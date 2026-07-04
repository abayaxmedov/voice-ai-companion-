from __future__ import annotations

from companion_core.contracts import (
    AgentProfile,
    LLMResponse,
    ProviderHealth,
    ProviderKind,
    TranscriptResult,
    VoiceAnalysisResult,
)
from companion_core.providers.base import LLMProvider


class LocalCompanionLLMProvider(LLMProvider):
    provider_id = "local_companion"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            self.provider_id,
            ProviderKind.LLM,
            ready=True,
            status="local_rules",
            message="Local Uzbek response generator. Replace with DeepSeek/OpenAI/Ollama for full reasoning.",
        )

    def respond(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
    ) -> LLMResponse:
        text = _normalize(transcript.text)
        emotion = (analysis.emotion or "").lower()
        response = _response_for_text(text)
        mood = "thoughtful"
        if emotion in {"anxious", "fear", "sadness"}:
            mood = "reassuring"
            response = f"Tushundim, buni xotirjam ko'rib chiqamiz. {response}"
        return LLMResponse(
            response=response,
            mood=mood,
            behavior="speak",
            speech_style="brief",
            debug_reason=f"{self.provider_id} response for {agent.agent_id}: {text}",
        )


def _normalize(text: str) -> str:
    return " ".join(text.strip().split())


def _response_for_text(text: str) -> str:
    lower = text.lower()
    if not text:
        return "Ovozingiz aniq eshitilmadi. Iltimos, savolni yana bir marta qisqaroq qilib ayting."
    if any(word in lower for word in ("salom", "assalomu", "assalom")):
        return "Salom. Sizni eshitdim. Qaysi ishni birinchi bo'lib bajarishimizni ayting."
    if any(word in lower for word in ("nima qila olasan", "nimalar qila olasan", "qila olasanmi")):
        return (
            "Men ovozingizni matnga aylantirib, Uzbek tilida javob tayyorlayman va "
            "ElevenLabs orqali ovoz bilan qaytaraman. Keyingi bosqichda real LLM ulanganda "
            "murakkab topshiriqlarni ham bajaraman."
        )
    if any(word in lower for word in ("rahmat", "tashakkur")):
        return "Marhamat. Davom etamiz, keyingi savolingizni ayting."
    if "?" in text or any(word in lower for word in ("qanday", "nega", "qayer", "qachon", "kim", "nima")):
        return (
            f"Savolingizni tushundim: {text}. Hozirgi lokal rejimda qisqa javob beraman: "
            "bu qism ishlayapti, endi uni real LLM bilan kuchaytirsak javoblar ancha aqlli bo'ladi."
        )
    return (
        f"Siz shunday dedingiz: {text}. Men ovozni qabul qildim va ElevenLabs orqali javob "
        "qaytaryapman. Endi shu oqim ustiga real AI mantiqini ulashga tayyormiz."
    )
