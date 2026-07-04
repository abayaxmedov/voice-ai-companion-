from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from companion_core.contracts import (
    ProviderHealth,
    ProviderKind,
    TranscriptResult,
    VoiceAnalysisResult,
)
from companion_core.providers.base import VoiceAnalysisProvider
from companion_core.providers.hume import HumeAnalysisClient, hume_result_from_payload


@dataclass(frozen=True)
class HumeVoiceAnalysisProvider(VoiceAnalysisProvider):
    """Adapter boundary for voice expression/prosody analysis platforms."""

    api_key_env: str
    api_key_configured: bool
    base_url: str = "https://api.hume.ai"
    client: HumeAnalysisClient | None = None
    provider_id: str = "hume"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            self.provider_id,
            ProviderKind.VOICE_ANALYSIS,
            ready=self.api_key_configured,
            status="configured" if self.api_key_configured else "missing_key",
            message=(
                f"Emotion/prosody adapter ready for {self.base_url}."
                if self.api_key_configured
                else f"Set {self.api_key_env} to enable Hume."
            ),
        )

    def analyze(self, audio_ref: str | None, transcript: TranscriptResult) -> VoiceAnalysisResult:
        if not self.api_key_configured:
            return VoiceAnalysisResult.unavailable(self.provider_id, f"Missing {self.api_key_env}.")
        if not audio_ref:
            return VoiceAnalysisResult.unavailable(self.provider_id, "Hume requires an audio_ref.")
        if self.client is None:
            return VoiceAnalysisResult.unavailable(
                self.provider_id,
                "Hume remote client is not connected yet. Use HUME_FIXTURE_PATH for local mapping tests.",
            )
        payload: dict[str, Any] = self.client.analyze_audio(audio_ref, transcript)
        result = hume_result_from_payload(payload, transcript)
        if result.provider_id == self.provider_id:
            return result
        return VoiceAnalysisResult(
            provider_id=self.provider_id,
            status=result.status,
            language=result.language,
            language_confidence=result.language_confidence,
            sentiment=result.sentiment,
            emotion=result.emotion,
            speaking_rate_wpm=result.speaking_rate_wpm,
            audio_quality=result.audio_quality,
            warnings=result.warnings,
            raw_summary=result.raw_summary,
        )


@dataclass(frozen=True)
class AssemblyAIVoiceAnalysisProvider(VoiceAnalysisProvider):
    """Adapter boundary for speech intelligence analysis."""

    api_key_env: str
    api_key_configured: bool
    provider_id: str = "assemblyai"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            self.provider_id,
            ProviderKind.VOICE_ANALYSIS,
            ready=self.api_key_configured,
            status="configured" if self.api_key_configured else "missing_key",
            message=None
            if self.api_key_configured
            else f"Set {self.api_key_env} to enable AssemblyAI.",
        )

    def analyze(self, audio_ref: str | None, transcript: TranscriptResult) -> VoiceAnalysisResult:
        raise NotImplementedError("AssemblyAI integration requires provider HTTP client.")


@dataclass(frozen=True)
class DeepgramVoiceAnalysisProvider(VoiceAnalysisProvider):
    """Adapter boundary for STT analytics/speech intelligence."""

    api_key_env: str
    api_key_configured: bool
    provider_id: str = "deepgram"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            self.provider_id,
            ProviderKind.VOICE_ANALYSIS,
            ready=self.api_key_configured,
            status="configured" if self.api_key_configured else "missing_key",
            message=None if self.api_key_configured else f"Set {self.api_key_env} to enable Deepgram.",
        )

    def analyze(self, audio_ref: str | None, transcript: TranscriptResult) -> VoiceAnalysisResult:
        raise NotImplementedError("Deepgram integration requires provider HTTP/WebSocket client.")
