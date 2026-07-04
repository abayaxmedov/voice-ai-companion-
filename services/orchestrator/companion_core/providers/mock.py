from __future__ import annotations

from companion_core.contracts import (
    AgentProfile,
    LLMResponse,
    ProviderHealth,
    ProviderKind,
    TTSResult,
    TranscriptResult,
    VoiceAnalysisResult,
)
from companion_core.providers.base import LLMProvider, STTProvider, TTSProvider, VoiceAnalysisProvider


class MockSTTProvider(STTProvider):
    provider_id = "mock_stt"

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider_id, ProviderKind.STT, ready=True, status="mock")

    def transcribe(self, audio_ref: str, language: str) -> TranscriptResult:
        return TranscriptResult(
            text="Salom, bugun Toshkentda ob-havo qanday?",
            language=language,
            confidence=0.99,
            provider_id=self.provider_id,
        )


class LocalVoiceAnalysisProvider(VoiceAnalysisProvider):
    provider_id = "local_voice_analysis"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            self.provider_id,
            ProviderKind.VOICE_ANALYSIS,
            ready=True,
            status="local_basic",
        )

    def analyze(self, audio_ref: str | None, transcript: TranscriptResult) -> VoiceAnalysisResult:
        words = transcript.text.split()
        return VoiceAnalysisResult(
            provider_id=self.provider_id,
            status="ok",
            language=transcript.language,
            language_confidence=transcript.confidence,
            sentiment="neutral",
            emotion="attentive",
            speaking_rate_wpm=max(90.0, min(150.0, len(words) * 12.0)),
            audio_quality="unknown" if audio_ref is None else "not_measured",
            raw_summary={"word_count": len(words)},
        )


class MockLLMProvider(LLMProvider):
    provider_id = "mock_llm"

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider_id, ProviderKind.LLM, ready=True, status="mock")

    def respond(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
    ) -> LLMResponse:
        del analysis
        return LLMResponse(
            response=(
                "Albatta. Hozir shu savol bo'yicha qisqa va aniq javob tayyorlayman."
            ),
            mood="thoughtful",
            behavior="speak",
            speech_style="brief",
            debug_reason=f"mock response for {agent.agent_id}: {transcript.text}",
        )


class MockTTSProvider(TTSProvider):
    provider_id = "mock_tts"

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider_id, ProviderKind.TTS, ready=True, status="mock")

    def synthesize(self, text: str, voice_profile_id: str, language: str) -> TTSResult:
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")
        return TTSResult(
            audio_ref=f"mock://{voice_profile_id}/turn.wav",
            provider_id=self.provider_id,
            duration_ms=max(700, len(text.split()) * 280),
            sample_rate_hz=24000,
            timing={"language": language},
        )

