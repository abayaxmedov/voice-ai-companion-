from __future__ import annotations

from dataclasses import dataclass, field

from companion_core.contracts import ProviderHealth
from companion_core.providers.base import LLMProvider, STTProvider, TTSProvider, VoiceAnalysisProvider


@dataclass
class ProviderRegistry:
    stt: dict[str, STTProvider] = field(default_factory=dict)
    llm: dict[str, LLMProvider] = field(default_factory=dict)
    tts: dict[str, TTSProvider] = field(default_factory=dict)
    voice_analysis: dict[str, VoiceAnalysisProvider] = field(default_factory=dict)

    def register_stt(self, provider: STTProvider) -> None:
        self.stt[provider.provider_id] = provider

    def register_llm(self, provider: LLMProvider) -> None:
        self.llm[provider.provider_id] = provider

    def register_tts(self, provider: TTSProvider) -> None:
        self.tts[provider.provider_id] = provider

    def register_voice_analysis(self, provider: VoiceAnalysisProvider) -> None:
        self.voice_analysis[provider.provider_id] = provider

    def require_stt(self, provider_id: str) -> STTProvider:
        return self.stt[provider_id]

    def require_llm(self, provider_id: str) -> LLMProvider:
        return self.llm[provider_id]

    def require_tts(self, provider_id: str) -> TTSProvider:
        return self.tts[provider_id]

    def require_voice_analysis(self, provider_id: str) -> VoiceAnalysisProvider:
        return self.voice_analysis[provider_id]

    def all_health(self) -> list[ProviderHealth]:
        providers = [
            *self.stt.values(),
            *self.llm.values(),
            *self.tts.values(),
            *self.voice_analysis.values(),
        ]
        return [provider.health() for provider in providers]
