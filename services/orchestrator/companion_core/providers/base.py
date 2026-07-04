from __future__ import annotations

from abc import ABC, abstractmethod

from companion_core.contracts import (
    AgentProfile,
    LLMResponse,
    ProviderHealth,
    TTSResult,
    TranscriptResult,
    VoiceAnalysisResult,
)


class STTProvider(ABC):
    provider_id: str

    @abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    def transcribe(self, audio_ref: str, language: str) -> TranscriptResult:
        raise NotImplementedError


class LLMProvider(ABC):
    provider_id: str

    @abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    def respond(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
    ) -> LLMResponse:
        raise NotImplementedError


class TTSProvider(ABC):
    provider_id: str

    @abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    def synthesize(self, text: str, voice_profile_id: str, language: str) -> TTSResult:
        raise NotImplementedError


class VoiceAnalysisProvider(ABC):
    provider_id: str

    @abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, audio_ref: str | None, transcript: TranscriptResult) -> VoiceAnalysisResult:
        raise NotImplementedError

