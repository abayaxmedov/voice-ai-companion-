from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
from pathlib import Path
import socket
from typing import Protocol
from urllib import error, parse, request
from uuid import uuid4

from companion_core.contracts import ProviderHealth, ProviderKind, TTSResult
from companion_core.providers.base import TTSProvider


class ElevenLabsClient(Protocol):
    def create_speech(
        self,
        *,
        api_key: str,
        voice_id: str,
        model_id: str,
        text: str,
        output_format: str,
        language_code: str | None,
    ) -> bytes:
        ...


# Prosodiya: LLM mood/speech_style -> ElevenLabs voice_settings.
# stability past = jonli/ekspressiv, baland = tinch/barqaror; style shunga teskari.
_BASE_VOICE_SETTINGS = {
    "stability": 0.55,
    "similarity_boost": 0.8,
    "style": 0.4,
    "use_speaker_boost": True,
}
_MOOD_VOICE_TWEAKS: dict[str, tuple[float, float]] = {
    # mood: (stability, style)
    "neutral": (0.55, 0.4),
    "happy": (0.45, 0.55),
    "excited": (0.32, 0.7),
    "thoughtful": (0.68, 0.3),
    "concerned": (0.6, 0.38),
    "apologetic": (0.7, 0.28),
    "reassuring": (0.72, 0.28),
}
_SPEECH_STYLE_DELTAS: dict[str, tuple[float, float]] = {
    # speech_style: (+stability, +style)
    "calm": (0.15, -0.1),
    "soft": (0.2, -0.15),
    "whisper": (0.2, -0.15),
    "excited": (-0.15, 0.15),
    "energetic": (-0.15, 0.15),
    "serious": (0.1, -0.05),
}


def voice_settings_for(mood: str, speech_style: str) -> dict[str, object]:
    stability, style = _MOOD_VOICE_TWEAKS.get(
        (mood or "neutral").lower(), _MOOD_VOICE_TWEAKS["neutral"]
    )
    d_st, d_style = _SPEECH_STYLE_DELTAS.get((speech_style or "normal").lower(), (0.0, 0.0))
    settings = dict(_BASE_VOICE_SETTINGS)
    settings["stability"] = round(min(1.0, max(0.0, stability + d_st)), 2)
    settings["style"] = round(min(1.0, max(0.0, style + d_style)), 2)
    return settings


@dataclass(frozen=True)
class ElevenLabsHttpClient:
    base_url: str = "https://api.elevenlabs.io"
    timeout_seconds: float = 30.0

    def create_speech(
        self,
        *,
        api_key: str,
        voice_id: str,
        model_id: str,
        text: str,
        output_format: str,
        language_code: str | None,
        voice_settings: dict | None = None,
    ) -> bytes:
        endpoint = _elevenlabs_tts_url(self.base_url, voice_id, output_format)
        payload: dict[str, object] = {
            "text": text,
            "model_id": model_id,
        }
        if language_code:
            payload["language_code"] = language_code
        if voice_settings:
            payload["voice_settings"] = voice_settings

        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": _accept_header_for_output_format(output_format),
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            },
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                audio = response.read()
        except error.HTTPError as exc:
            raise RuntimeError(_elevenlabs_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"ElevenLabs synthesis request failed: {exc}") from exc

        if not audio:
            raise RuntimeError("ElevenLabs synthesis returned an empty audio response.")
        return audio

    def create_speech_with_timing(
        self,
        *,
        api_key: str,
        voice_id: str,
        model_id: str,
        text: str,
        output_format: str,
        language_code: str | None,
        voice_settings: dict | None = None,
    ) -> tuple[bytes, dict | None]:
        """Synthesis + character-level timestamps (phoneme-accurate lip-sync).

        Uses the /with-timestamps endpoint; the caller falls back to plain
        synthesis if this raises.
        """
        endpoint = _elevenlabs_tts_timestamps_url(self.base_url, voice_id, output_format)
        payload: dict[str, object] = {
            "text": text,
            "model_id": model_id,
        }
        if language_code:
            payload["language_code"] = language_code
        if voice_settings:
            payload["voice_settings"] = voice_settings

        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            },
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_elevenlabs_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"ElevenLabs synthesis request failed: {exc}") from exc

        audio = base64.b64decode(body.get("audio_base64") or "")
        if not audio:
            raise RuntimeError("ElevenLabs with-timestamps returned no audio.")
        alignment = body.get("normalized_alignment") or body.get("alignment") or None
        if not isinstance(alignment, dict):
            alignment = None
        return audio, alignment

    def stream_speech_with_timing(
        self,
        *,
        api_key: str,
        voice_id: str,
        model_id: str,
        text: str,
        output_format: str,
        language_code: str | None,
        voice_settings: dict | None = None,
    ):
        """Chunk generatori: (pcm_bytes, alignment|None) — past kechikish.

        /stream/with-timestamps NDJSON qaytaradi; har satr audio_base64 va
        (bo'lsa) shu bo'lakning character-alignmenti.
        """
        endpoint = _elevenlabs_tts_stream_url(self.base_url, voice_id, output_format)
        payload: dict[str, object] = {
            "text": text,
            "model_id": model_id,
        }
        if language_code:
            payload["language_code"] = language_code
        if voice_settings:
            payload["voice_settings"] = voice_settings

        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/x-ndjson",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.strip()
                    if not line:
                        continue
                    body = json.loads(line)
                    audio = base64.b64decode(body.get("audio_base64") or "")
                    alignment = (
                        body.get("normalized_alignment") or body.get("alignment") or None
                    )
                    if not isinstance(alignment, dict):
                        alignment = None
                    if audio or alignment:
                        yield audio, alignment
        except error.HTTPError as exc:
            raise RuntimeError(_elevenlabs_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"ElevenLabs streaming failed: {exc}") from exc


@dataclass(frozen=True)
class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs adapter boundary.

    Real HTTP integration belongs here. Uzbek quality must be tested with a
    project-specific voice set; this adapter must not claim Uzbek is solved just
    because synthesis returns audio.
    """

    api_key_configured: bool
    api_key_env: str
    voice_id: str
    api_key: str = field(default="", repr=False, compare=False)
    model_id: str = "eleven_flash_v2_5"
    base_url: str = "https://api.elevenlabs.io"
    # PCM: WAV sifatida keshga yoziladi va lab-sinxron uchun audio-tahlil
    # (mouth curves) imkonini beradi. mp3 ga qaytarilsa tahlil o'chadi, xolos.
    output_format: str = "pcm_24000"
    language_code: str = "uz"
    speed: str = ""  # 0.7–1.2 (ElevenLabs voice_settings.speed); bo'sh = 1.0
    audio_cache_dir: str = "/private/tmp/voice-ai-companion/audio"
    client: ElevenLabsClient | None = field(default=None, repr=False, compare=False)
    provider_id: str = "elevenlabs"

    def _voice_settings(self, mood: str, speech_style: str) -> dict[str, object]:
        settings = voice_settings_for(mood, speech_style)
        speed = _parse_speed(self.speed)
        if speed is not None:
            settings["speed"] = speed
        return settings

    def health(self) -> ProviderHealth:
        if not self.api_key_configured or not self.api_key:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.TTS,
                ready=False,
                status="missing_key",
                message=f"Set {self.api_key_env} to enable ElevenLabs.",
            )
        if not self.voice_id:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.TTS,
                ready=False,
                status="missing_voice_id",
                message="Set ELEVENLABS_VOICE_ID for the Uzbek voice profile.",
            )
        return ProviderHealth(
            self.provider_id,
            ProviderKind.TTS,
            ready=True,
            status="configured",
            message=f"Model {self.model_id}; output {self.output_format}; live synthesis enabled.",
        )

    def synthesize(self, text: str, voice_profile_id: str, language: str) -> TTSResult:
        return self.synthesize_styled(text, voice_profile_id, language)

    def synthesize_styled(
        self,
        text: str,
        voice_profile_id: str,
        language: str,
        mood: str = "neutral",
        speech_style: str = "normal",
    ) -> TTSResult:
        del voice_profile_id
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Cannot synthesize empty text.")
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")
        if not self.voice_id:
            raise ValueError("ELEVENLABS_VOICE_ID is not configured.")

        language_code = _elevenlabs_language_code(self.language_code, language)
        voice_settings = self._voice_settings(mood, speech_style)
        client = self.client or ElevenLabsHttpClient(base_url=self.base_url)

        # Prefer the with-timestamps endpoint: character alignment powers
        # phoneme-accurate avatar lip-sync. Degrade to plain synthesis.
        audio: bytes | None = None
        alignment: dict | None = None
        timed_synthesis = getattr(client, "create_speech_with_timing", None)
        if callable(timed_synthesis):
            try:
                audio, alignment = timed_synthesis(
                    api_key=self.api_key,
                    voice_id=self.voice_id,
                    model_id=self.model_id,
                    text=normalized_text,
                    output_format=self.output_format,
                    language_code=language_code,
                    voice_settings=voice_settings,
                )
            except Exception:  # noqa: BLE001 - timestamps are an enhancement.
                audio = None
                alignment = None
        if audio is None:
            try:
                audio = client.create_speech(
                    api_key=self.api_key,
                    voice_id=self.voice_id,
                    model_id=self.model_id,
                    text=normalized_text,
                    output_format=self.output_format,
                    language_code=language_code,
                    voice_settings=voice_settings,
                )
            except TypeError:
                # Eski/mock klientlar voice_settings'ni bilmaydi.
                audio = client.create_speech(
                    api_key=self.api_key,
                    voice_id=self.voice_id,
                    model_id=self.model_id,
                    text=normalized_text,
                    output_format=self.output_format,
                    language_code=language_code,
                )

        sample_rate = _sample_rate_for_output_format(self.output_format)
        extension = _extension_for_output_format(self.output_format)
        codec = self.output_format.split("_", 1)[0].lower()
        pcm_bytes = len(audio)
        if codec == "pcm":
            # Xom PCM'ni WAV konteyneriga o'raymiz: <audio> o'ynata oladi va
            # backend audio-tahlil (og'iz egri chiziqlari) o'qiy oladi.
            audio = _wrap_pcm_as_wav(audio, sample_rate or 24000)
            extension = ".wav"

        duration_ms = _duration_ms_from_alignment(alignment)
        if duration_ms is None and codec == "pcm" and (sample_rate or 0) > 0:
            duration_ms = max(1, int(pcm_bytes / 2 / sample_rate * 1000))
        if duration_ms is None:
            duration_ms = _estimate_duration_ms(normalized_text)

        timing: dict[str, object] = {
            "model_id": self.model_id,
            "output_format": self.output_format,
            "language": language,
            "language_code": language_code,
        }
        if alignment:
            timing["alignment"] = alignment

        cache_path = self._write_audio(audio, extension)
        return TTSResult(
            audio_ref=f"file://{cache_path}",
            provider_id=self.provider_id,
            duration_ms=duration_ms,
            sample_rate_hz=sample_rate,
            timing=timing,
        )

    def synthesize_stream(
        self,
        text: str,
        voice_profile_id: str,
        language: str,
        mood: str = "neutral",
        speech_style: str = "normal",
    ):
        """PCM chunk generatori: (pcm_bytes, alignment|None).

        Faqat pcm_* formatlarda ishlaydi (WebAudio to'g'ridan-to'g'ri ijro
        etadi). Xato bo'lsa chaqiruvchi klassik synthesize'ga qaytadi.
        """
        del voice_profile_id
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Cannot synthesize empty text.")
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")
        if not self.voice_id:
            raise ValueError("ELEVENLABS_VOICE_ID is not configured.")
        if self.output_format.split("_", 1)[0].lower() != "pcm":
            raise ValueError("Streaming requires a pcm_* ELEVENLABS_OUTPUT_FORMAT.")

        client = self.client or ElevenLabsHttpClient(base_url=self.base_url)
        streamer = getattr(client, "stream_speech_with_timing", None)
        if not callable(streamer):
            raise ValueError("TTS client does not support streaming.")
        yield from streamer(
            api_key=self.api_key,
            voice_id=self.voice_id,
            model_id=self.model_id,
            text=normalized_text,
            output_format=self.output_format,
            language_code=_elevenlabs_language_code(self.language_code, language),
            voice_settings=self._voice_settings(mood, speech_style),
        )

    def _write_audio(self, audio: bytes, extension: str | None = None) -> Path:
        cache_dir = Path(self.audio_cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        extension = extension or _extension_for_output_format(self.output_format)
        cache_path = cache_dir / f"elevenlabs-{uuid4()}{extension}"
        cache_path.write_bytes(audio)
        return cache_path


@dataclass(frozen=True)
class KokoroTTSProvider(TTSProvider):
    """Local Kokoro adapter boundary.

    Kokoro is the local/offline TTS path. Uzbek support is an R&D gate and must
    be validated through tests before it can be used as a release-quality voice.
    """

    model_path: str
    voice_name: str
    provider_id: str = "kokoro"

    def health(self) -> ProviderHealth:
        if not self.model_path:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.TTS,
                ready=False,
                status="missing_model",
                message="Set KOKORO_MODEL_PATH after the local Kokoro model is downloaded.",
            )
        if not self.voice_name:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.TTS,
                ready=False,
                status="missing_voice",
                message="Set KOKORO_VOICE_NAME for the local voice profile.",
            )
        return ProviderHealth(
            self.provider_id,
            ProviderKind.TTS,
            ready=True,
            status="configured",
            message="Local synthesis runtime is the next implementation step.",
        )

    def synthesize(self, text: str, voice_profile_id: str, language: str) -> TTSResult:
        raise NotImplementedError(
            "Kokoro local synthesis is intentionally not implemented in the scaffold."
        )


def _elevenlabs_tts_url(base_url: str, voice_id: str, output_format: str) -> str:
    encoded_voice_id = parse.quote(voice_id, safe="")
    query = parse.urlencode({"output_format": output_format})
    return f"{base_url.rstrip('/')}/v1/text-to-speech/{encoded_voice_id}?{query}"


def _elevenlabs_tts_timestamps_url(base_url: str, voice_id: str, output_format: str) -> str:
    encoded_voice_id = parse.quote(voice_id, safe="")
    query = parse.urlencode({"output_format": output_format})
    return (
        f"{base_url.rstrip('/')}/v1/text-to-speech/{encoded_voice_id}"
        f"/with-timestamps?{query}"
    )


def _elevenlabs_tts_stream_url(base_url: str, voice_id: str, output_format: str) -> str:
    encoded_voice_id = parse.quote(voice_id, safe="")
    query = parse.urlencode(
        {"output_format": output_format, "optimize_streaming_latency": 2}
    )
    return (
        f"{base_url.rstrip('/')}/v1/text-to-speech/{encoded_voice_id}"
        f"/stream/with-timestamps?{query}"
    )


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int) -> bytes:
    """Mono 16-bit PCM -> WAV (RIFF) container."""
    import struct

    return (
        struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + len(pcm),
            b"WAVE",
            b"fmt ",
            16,
            1,  # PCM
            1,  # mono
            sample_rate,
            sample_rate * 2,
            2,
            16,
            b"data",
            len(pcm),
        )
        + pcm
    )


def _duration_ms_from_alignment(alignment: dict | None) -> int | None:
    if not alignment:
        return None
    ends = alignment.get("character_end_times_seconds")
    if not ends:
        return None
    try:
        return max(1, int(float(ends[-1]) * 1000))
    except (TypeError, ValueError):
        return None


def _elevenlabs_http_error_message(exc: error.HTTPError) -> str:
    error_payload = _safe_error_payload(exc)
    detail = error_payload.get("detail") if isinstance(error_payload, dict) else None
    if isinstance(detail, dict):
        code = str(detail.get("code", ""))
        message = str(detail.get("message", ""))
        if "text_to_speech" in message:
            return (
                "ElevenLabs API key does not have text_to_speech permission. "
                "Create or update the key in ElevenLabs with the text_to_speech permission, "
                "then restart the local stack."
            )
        if code == "unauthorized":
            return (
                "ElevenLabs API key was rejected as unauthorized. "
                "Check that ELEVENLABS_API_KEY is copied correctly, active, and has text_to_speech permission."
            )
        if code:
            return f"ElevenLabs synthesis failed with HTTP {exc.code}: {code}."
    return f"ElevenLabs synthesis failed with HTTP {exc.code}."


def _safe_error_payload(exc: error.HTTPError) -> object:
    try:
        body = exc.read(2000).decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001 - error body is optional context.
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _accept_header_for_output_format(output_format: str) -> str:
    codec = output_format.split("_", 1)[0].lower()
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "pcm": "application/octet-stream",
        "ulaw": "application/octet-stream",
    }.get(codec, "application/octet-stream")


def _extension_for_output_format(output_format: str) -> str:
    codec = output_format.split("_", 1)[0].lower()
    return {
        "mp3": ".mp3",
        "wav": ".wav",
        "pcm": ".pcm",
        "ulaw": ".ulaw",
    }.get(codec, ".audio")


def _sample_rate_for_output_format(output_format: str) -> int | None:
    parts = output_format.split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _parse_speed(value: str) -> float | None:
    """ELEVENLABS_SPEED: 0.7–1.2 oralig'ida son; bo'sh/noto'g'ri = None (1.0)."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        speed = float(text)
    except ValueError:
        return None
    return round(min(1.2, max(0.7, speed)), 2)


def _language_code_from_locale(language: str) -> str | None:
    language_code = language.split("-", 1)[0].strip().lower()
    if len(language_code) != 2:
        return None
    return language_code


def _elevenlabs_language_code(configured_language_code: str, language: str) -> str | None:
    configured = configured_language_code.strip().lower()
    if configured in {"", "auto", "none", "default"}:
        return None
    return configured or _language_code_from_locale(language)


def _estimate_duration_ms(text: str) -> int:
    words = max(1, len(text.split()))
    return max(700, int(words * 310))
