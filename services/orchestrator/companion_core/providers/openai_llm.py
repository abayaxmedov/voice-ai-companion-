from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import socket
from typing import Any, Protocol
from urllib import error, request
from zoneinfo import ZoneInfo

from companion_core.contracts import (
    AgentProfile,
    LLMResponse,
    ProviderHealth,
    ProviderKind,
    TranscriptResult,
    VoiceAnalysisResult,
)
from companion_core.providers.base import LLMProvider

_ALLOWED_MOODS = {"neutral", "happy", "thoughtful", "concerned", "excited", "apologetic"}
_ALLOWED_BEHAVIORS = {"idle", "listen", "think", "speak", "explain", "celebrate", "confirm"}
_ALLOWED_SPEECH_STYLES = {"brief", "normal", "explanatory"}
_ALLOWED_SAFETY = {"normal", "confirm_required", "deny", "sensitive"}

_SYSTEM_PROMPT = """Sen ovozli o'zbek AI hamrohsan. Foydalanuvchi bilan faqat ovoz orqali suhbatlashasan; javobing avatar ovozi bilan aytiladi.

Qoidalar:
- Har doim o'zbek tilida (lotin yozuvida) javob ber. Foydalanuvchi rus yoki ingliz so'z aralashtirsa ham, javob o'zbekcha bo'lsin.
- Javob og'zaki nutq uchun: qisqa, tabiiy, 1-3 gap. Markdown, ro'yxat, jadval, kod ishlatma.
- Raqam va vaqtlarni imkon qadar so'z bilan ifodala.
- Samimiy, hurmatli va professional ohangda gapir.

Faqat quyidagi JSON formatida javob qaytar (boshqa hech narsa yozma):
{
  "response": "avatar aytadigan o'zbekcha matn",
  "mood": "neutral|happy|thoughtful|concerned|excited|apologetic",
  "behavior": "idle|listen|think|speak|explain|celebrate|confirm",
  "speech_style": "brief|normal|explanatory",
  "safety_level": "normal|confirm_required|deny|sensitive",
  "debug_reason": "qisqa ichki izoh (ixtiyoriy)"
}"""

_REPAIR_PROMPT = (
    "Oldingi javobing talab qilingan JSON sxemaga mos kelmadi. "
    "Endi FAQAT to'g'ri JSON obyekt qaytar: response (bo'sh bo'lmagan o'zbekcha matn, "
    "markdown belgilarisiz), mood, behavior, speech_style, safety_level."
)


class OpenAIChatClient(Protocol):
    def create_chat_completion(
        self,
        *,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class OpenAIChatHttpClient:
    base_url: str = "https://api.openai.com"
    timeout_seconds: float = 60.0

    def create_chat_completion(
        self,
        *,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        body = json.dumps(
            {
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.6,
                "max_tokens": 400,
            }
        ).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(_openai_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"OpenAI chat request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI chat returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI chat returned an invalid response.")
        return payload


@dataclass(frozen=True)
class OpenAILLMProvider(LLMProvider):
    api_key_configured: bool
    api_key_env: str
    api_key: str = field(default="", repr=False, compare=False)
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com"
    client: OpenAIChatClient | None = field(default=None, repr=False, compare=False)
    provider_id: str = "openai_llm"

    def health(self) -> ProviderHealth:
        if not self.api_key_configured or not self.api_key:
            return ProviderHealth(
                self.provider_id,
                ProviderKind.LLM,
                ready=False,
                status="missing_key",
                message=f"Set {self.api_key_env} to enable the OpenAI language model.",
            )
        return ProviderHealth(
            self.provider_id,
            ProviderKind.LLM,
            ready=True,
            status="configured",
            message=f"Model {self.model}; Uzbek voice response contract.",
        )

    def respond(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
    ) -> LLMResponse:
        return self.respond_with_history(transcript, analysis, agent, [])

    def respond_with_history(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
        history: list[dict[str, str]],
    ) -> LLMResponse:
        if not self.api_key_configured or not self.api_key:
            raise ValueError(f"{self.api_key_env} is not configured.")

        client = self.client or OpenAIChatHttpClient(base_url=self.base_url)
        messages = self._build_messages(transcript, analysis, agent, history)

        payload = client.create_chat_completion(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
        )
        try:
            return self._parse_response(payload)
        except (KeyError, ValueError, TypeError) as first_error:
            # TZ 11: one repair retry with the schema error before failing over.
            repair_messages = messages + [
                {"role": "assistant", "content": _raw_content(payload) or "invalid"},
                {"role": "user", "content": f"{_REPAIR_PROMPT} Xato: {first_error}"},
            ]
            payload = client.create_chat_completion(
                api_key=self.api_key,
                model=self.model,
                messages=repair_messages,
            )
            return self._parse_response(payload)

    def _build_messages(
        self,
        transcript: TranscriptResult,
        analysis: VoiceAnalysisResult,
        agent: AgentProfile,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        system = _SYSTEM_PROMPT
        profile_block = _profile_block(agent)
        if profile_block:
            system = f"{system}\n\n{profile_block}"

        context_notes: list[str] = []
        if analysis.emotion:
            context_notes.append(f"Foydalanuvchi ovozidagi ehtimoliy hissiyot: {analysis.emotion}.")
        if analysis.sentiment:
            context_notes.append(f"Umumiy kayfiyat: {analysis.sentiment}.")
        user_content = transcript.text.strip()
        if context_notes:
            user_content = f"{user_content}\n\n[Ovoz tahlili: {' '.join(context_notes)}]"

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for item in (history or [])[-12:]:
            role = item.get("role", "")
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_content})
        return messages

    def _parse_response(self, payload: dict[str, Any]) -> LLMResponse:
        content = _raw_content(payload)
        if not content:
            raise ValueError("OpenAI chat returned an empty message.")
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("OpenAI response JSON must be an object.")

        response_text = str(data.get("response", "")).strip()
        if not response_text:
            raise ValueError("OpenAI response field is empty.")

        llm_response = LLMResponse(
            response=response_text,
            mood=_pick(data.get("mood"), _ALLOWED_MOODS, "neutral"),
            behavior=_pick(data.get("behavior"), _ALLOWED_BEHAVIORS, "speak"),
            speech_style=_pick(data.get("speech_style"), _ALLOWED_SPEECH_STYLES, "normal"),
            safety_level=_pick(data.get("safety_level"), _ALLOWED_SAFETY, "normal"),
            debug_reason=_optional_str(data.get("debug_reason")),
        )
        llm_response.validate_for_speech()
        return llm_response


def _vibe_note(value: float, low: str, mid: str, high: str) -> str:
    if value < 0.34:
        return low
    if value < 0.67:
        return mid
    return high


def _profile_block(agent: AgentProfile) -> str:
    """Unclaw-style vibe/profile settings rendered as system prompt guidance."""
    lines: list[str] = []
    if agent.display_name.strip():
        lines.append(f"Sening isming: {agent.display_name.strip()}.")
    if agent.user_name.strip():
        lines.append(
            f"Foydalanuvchining ismi: {agent.user_name.strip()}. "
            "O'rni kelganda unga ismi bilan murojaat qil."
        )
    if agent.city.strip():
        lines.append(f"Foydalanuvchi shahri: {agent.city.strip()}.")
    if agent.timezone.strip():
        try:
            now_local = datetime.now(ZoneInfo(agent.timezone.strip()))
            lines.append(
                "Hozirgi mahalliy sana va vaqt: "
                f"{now_local.strftime('%Y-%m-%d %H:%M')} ({agent.timezone.strip()})."
            )
        except (KeyError, ValueError, OSError):
            pass
    if agent.hobbies:
        lines.append("Foydalanuvchi qiziqishlari: " + ", ".join(agent.hobbies) + ".")

    lines.append(
        "Muloqot uslubi: "
        + _vibe_note(
            agent.vibe_formality,
            "juda samimiy va do'stona ohangda gapir;",
            "samimiy, lekin professional ohangda gapir;",
            "rasmiy va odobli ohangda gapir;",
        )
        + " "
        + _vibe_note(
            agent.vibe_humor,
            "hazilni deyarli ishlatma;",
            "o'rni kelganda yengil hazil qo'sh;",
            "quvnoq va hazilkash bo'l;",
        )
        + " "
        + _vibe_note(
            agent.vibe_directness,
            "yumshoq va ehtiyotkor bo'l;",
            "halol va aniq bo'l;",
            "to'g'ridan-to'g'ri va dadil gapir;",
        )
        + " "
        + _vibe_note(
            agent.vibe_verbosity,
            "javoblaring juda qisqa bo'lsin (bir-ikki gap).",
            "javoblaring qisqa bo'lsin (bir-uch gap).",
            "kerak bo'lsa batafsilroq javob ber (uch-besh gap).",
        )
    )
    if agent.persona.strip():
        lines.append(f"Qo'shimcha persona: {agent.persona.strip()}")
    return "\n".join(lines)


def _raw_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    return str(message.get("content", "")).strip()


def _pick(value: object, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else default


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _openai_http_error_message(exc: error.HTTPError) -> str:
    if exc.code == 401:
        return (
            "OpenAI API key was rejected as unauthorized. "
            "Check that OPENAI_API_KEY is copied correctly and active."
        )
    if exc.code == 429:
        return "OpenAI rate limit or quota reached. Try again shortly or check billing."
    try:
        body = exc.read(2000).decode("utf-8", errors="replace")
        detail = json.loads(body).get("error", {})
        message = str(detail.get("message", "")).strip()
        if message:
            return f"OpenAI chat failed with HTTP {exc.code}: {message[:200]}"
    except Exception:  # noqa: BLE001 - error body is optional context.
        pass
    return f"OpenAI chat failed with HTTP {exc.code}."
