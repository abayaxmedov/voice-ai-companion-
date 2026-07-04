from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from companion_core.contracts import (
    AgentProfile,
    AvatarPlaybackJob,
    TranscriptResult,
    TTSResult,
    VoiceAnalysisResult,
    VoiceTurnRequest,
    VoiceTurnResult,
)
from companion_core.pipeline.audio_mouth import StreamingMouthAnalyzer, mouth_curves_for_tts
from companion_core.pipeline.normalization import normalize_speech_text
from companion_core.pipeline.visemes import generate_viseme_timeline, visemes_from_alignment
from companion_core.providers import ProviderRegistry
from companion_core.providers.hume import avatar_mood_from_emotion
from companion_core.providers.tts import _wrap_pcm_as_wav

LLM_FALLBACK_PROVIDER_ID = "local_companion"

EmitFn = Callable[[dict[str, Any]], None]


class StreamingUnsupported(RuntimeError):
    """TTS provayder streaming'ni qo'llamaydi — klassik yo'l ishlatilsin."""


@dataclass(frozen=True)
class PipelineProviderSelection:
    stt_provider_id: str
    llm_provider_id: str
    tts_provider_id: str
    voice_analysis_provider_id: str


class VoiceTurnPipeline:
    def __init__(self, registry: ProviderRegistry, selection: PipelineProviderSelection) -> None:
        self._registry = registry
        self._selection = selection

    def run(
        self,
        request: VoiceTurnRequest,
        agent: AgentProfile,
        history: list[dict[str, str]] | None = None,
    ) -> VoiceTurnResult:
        request.validate()
        turn_id = str(uuid4())
        latency: dict[str, int] = {}

        transcript = self._transcribe(request, latency)
        analysis = self._analyze(request.audio_ref, transcript, latency)
        llm_response = self._respond(transcript, analysis, agent, latency, history or [])
        llm_response.validate_for_speech()
        speakable = normalize_speech_text(llm_response.response)
        tts = self._synthesize(
            speakable,
            agent,
            latency,
            mood=llm_response.mood,
            speech_style=llm_response.speech_style,
        )

        try:
            mouth_curves = mouth_curves_for_tts(tts)
        except Exception:  # noqa: BLE001 - tahlil hech qachon turn'ni yiqitmasin.
            mouth_curves = None

        avatar_job = AvatarPlaybackJob(
            turn_id=turn_id,
            avatar_id=agent.avatar_id,
            audio_ref=tts.audio_ref,
            mood=avatar_mood_from_emotion(llm_response.mood, analysis),
            behavior=llm_response.behavior,
            # Phoneme-accurate lip-sync: real TTS character alignment when the
            # provider returned it, Uzbek grapheme->viseme fallback otherwise.
            visemes=generate_viseme_timeline(
                speakable,
                tts.duration_ms,
                alignment=tts.timing.get("alignment") if tts.timing else None,
            ),
            mouth_curves=mouth_curves,
        )

        return VoiceTurnResult(
            turn_id=turn_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
            transcript=transcript,
            analysis=analysis,
            llm_response=llm_response,
            tts=tts,
            avatar_job=avatar_job,
            latency_ms=latency,
        )

    def run_streaming(
        self,
        request: VoiceTurnRequest,
        agent: AgentProfile,
        history: list[dict[str, str]] | None,
        emit: EmitFn,
    ) -> VoiceTurnResult:
        """Past kechikishli turn: TTS chunk'lari kelishi bilan emit qilinadi.

        Hodisalar: {"type":"meta",...} -> {"type":"audio",...}* ; yakuniy
        VoiceTurnResult qaytadi (tarix/bridge uchun). Provayder streaming'ni
        qo'llamasa StreamingUnsupported ko'tariladi (birinchi emit'dan OLDIN).
        """
        request.validate()
        provider = self._registry.require_tts(self._selection.tts_provider_id)
        stream_fn = getattr(provider, "synthesize_stream", None)
        if not callable(stream_fn):
            raise StreamingUnsupported(
                f"{self._selection.tts_provider_id} does not support streaming."
            )

        turn_id = str(uuid4())
        latency: dict[str, int] = {}
        transcript = self._transcribe(request, latency)
        analysis = self._analyze(request.audio_ref, transcript, latency)
        llm_response = self._respond(transcript, analysis, agent, latency, history or [])
        llm_response.validate_for_speech()
        speakable = normalize_speech_text(llm_response.response)
        mood = avatar_mood_from_emotion(llm_response.mood, analysis)

        emit(
            {
                "type": "meta",
                "turn_id": turn_id,
                "transcript": transcript,
                "llm_response": llm_response,
                "mood": mood,
                "latency_ms": dict(latency),
            }
        )

        sample_rate = _provider_sample_rate(provider)
        analyzer = StreamingMouthAnalyzer(sample_rate)
        pcm_all = bytearray()
        align: dict[str, list] = {
            "characters": [],
            "character_start_times_seconds": [],
            "character_end_times_seconds": [],
        }
        start = perf_counter()
        first_chunk_ms: int | None = None

        for chunk, alignment in stream_fn(
            speakable,
            agent.voice_profile_id,
            agent.language,
            mood=llm_response.mood,
            speech_style=llm_response.speech_style,
        ):
            if first_chunk_ms is None:
                first_chunk_ms = _elapsed_ms(start)
                latency["tts_first_chunk_ms"] = first_chunk_ms
            if alignment:
                # MUHIM: ba'zi oqimlarda chunk alignmenti 0 dan boshlanadi
                # (chunk-relativ). Kumulyativ qo'shishdan oldin shu holatni
                # aniqlab, shu paytgacha kelgan audio davomiyligi bilan
                # siljitamiz — aks holda lablar "orqaga sakraydi".
                _merge_alignment(align, alignment, len(pcm_all) / 2.0 / sample_rate)
            if not chunk:
                continue
            pcm_all.extend(chunk)
            curves_delta = analyzer.feed(chunk)
            visemes = (
                visemes_from_alignment(align) if align["characters"] else ()
            )
            emit(
                {
                    "type": "audio",
                    "pcm_b64": base64.b64encode(chunk).decode("ascii"),
                    "sample_rate": sample_rate,
                    "curves": curves_delta,
                    "visemes": visemes,
                }
            )

        latency["tts_ms"] = _elapsed_ms(start)
        if not pcm_all:
            raise RuntimeError("Streaming TTS returned no audio.")

        # Yakuniy WAV keshga (tarix/qayta ijro/mock bridge uchun).
        duration_ms = max(1, int(len(pcm_all) / 2 / sample_rate * 1000))
        cache_dir = Path(
            getattr(provider, "audio_cache_dir", "/private/tmp/voice-ai-companion/audio")
        ).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"stream-{turn_id}.wav"
        cache_path.write_bytes(_wrap_pcm_as_wav(bytes(pcm_all), sample_rate))

        final_alignment = align if align["characters"] else None
        tts = TTSResult(
            audio_ref=f"file://{cache_path}",
            provider_id=getattr(provider, "provider_id", "unknown"),
            duration_ms=duration_ms,
            sample_rate_hz=sample_rate,
            timing={"streamed": True, **({"alignment": final_alignment} if final_alignment else {})},
        )
        avatar_job = AvatarPlaybackJob(
            turn_id=turn_id,
            avatar_id=agent.avatar_id,
            audio_ref=tts.audio_ref,
            mood=mood,
            behavior=llm_response.behavior,
            visemes=generate_viseme_timeline(speakable, duration_ms, alignment=final_alignment),
        )
        return VoiceTurnResult(
            turn_id=turn_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
            transcript=transcript,
            analysis=analysis,
            llm_response=llm_response,
            tts=tts,
            avatar_job=avatar_job,
            latency_ms=latency,
        )

    def _transcribe(self, request: VoiceTurnRequest, latency: dict[str, int]) -> TranscriptResult:
        if request.transcript_override is not None:
            return TranscriptResult(
                text=request.transcript_override,
                language=request.user_locale,
                confidence=1.0,
                provider_id="transcript_override",
            )

        start = perf_counter()
        provider = self._registry.require_stt(self._selection.stt_provider_id)
        result = provider.transcribe(request.audio_ref or "", request.user_locale)
        latency["stt_ms"] = _elapsed_ms(start)
        return result

    def _analyze(
        self,
        audio_ref: str | None,
        transcript: TranscriptResult,
        latency: dict[str, int],
    ) -> VoiceAnalysisResult:
        start = perf_counter()
        provider = self._registry.require_voice_analysis(
            self._selection.voice_analysis_provider_id
        )
        try:
            result = provider.analyze(audio_ref, transcript)
        except Exception as exc:  # noqa: BLE001 - provider boundary must degrade safely.
            result = VoiceAnalysisResult.unavailable(provider.provider_id, str(exc))
        latency["voice_analysis_ms"] = _elapsed_ms(start)
        return result

    def _respond(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
        latency: dict[str, int],
        history: list[dict[str, str]],
    ):
        start = perf_counter()
        provider = self._registry.require_llm(self._selection.llm_provider_id)
        try:
            responder = getattr(provider, "respond_with_history", None)
            if callable(responder) and history:
                result = responder(transcript, analysis, agent, history)
            else:
                result = provider.respond(transcript, analysis, agent)
            result.validate_for_speech()
        except Exception as exc:  # noqa: BLE001 - TZ 11: fail over instead of crashing the turn.
            if (
                provider.provider_id == LLM_FALLBACK_PROVIDER_ID
                or LLM_FALLBACK_PROVIDER_ID not in self._registry.llm
            ):
                raise
            fallback = self._registry.require_llm(LLM_FALLBACK_PROVIDER_ID)
            result = fallback.respond(transcript, analysis, agent)
            result = replace(
                result,
                debug_reason=(
                    f"fallback from {provider.provider_id}: {exc}"
                ),
            )
        latency["llm_ms"] = _elapsed_ms(start)
        return result

    def _synthesize(
        self,
        speakable: str,
        agent: AgentProfile,
        latency: dict[str, int],
        mood: str = "neutral",
        speech_style: str = "normal",
    ):
        start = perf_counter()
        provider = self._registry.require_tts(self._selection.tts_provider_id)
        # Prosodiya: kayfiyat ovoz sozlamalariga ta'sir qiladi (qo'llagan
        # provayderlarda); qolganlari oddiy synthesize bilan ishlayveradi.
        styled = getattr(provider, "synthesize_styled", None)
        if callable(styled):
            result = styled(
                speakable,
                agent.voice_profile_id,
                agent.language,
                mood=mood,
                speech_style=speech_style,
            )
        else:
            result = provider.synthesize(speakable, agent.voice_profile_id, agent.language)
        latency["tts_ms"] = _elapsed_ms(start)
        return result


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _merge_alignment(
    total: dict[str, list],
    incoming: dict,
    audio_seconds_before_chunk: float,
) -> None:
    chars = incoming.get("characters") or []
    starts = incoming.get("character_start_times_seconds") or []
    ends = incoming.get("character_end_times_seconds") or []
    if not chars or len(chars) != len(starts) or len(chars) != len(ends):
        return
    offset = 0.0
    if total["character_end_times_seconds"]:
        last_end = float(total["character_end_times_seconds"][-1])
        try:
            first_start = float(starts[0])
        except (TypeError, ValueError):
            return
        # Agar yangi vaqtlar orqaga qaytsa — chunk-relativ deb hisoblab,
        # oldin kelgan audio davomiyligiga siljitamiz.
        if first_start < last_end - 0.05:
            offset = max(audio_seconds_before_chunk, last_end)
    total["characters"].extend(chars)
    total["character_start_times_seconds"].extend(float(s) + offset for s in starts)
    total["character_end_times_seconds"].extend(float(e) + offset for e in ends)


def _provider_sample_rate(provider: object) -> int:
    output_format = str(getattr(provider, "output_format", "pcm_24000"))
    parts = output_format.split("_")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 24000
