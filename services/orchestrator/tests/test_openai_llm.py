from __future__ import annotations

import json
from typing import Any
import unittest

from companion_core.contracts import AgentProfile, TranscriptResult, VoiceAnalysisResult
from companion_core.providers.openai_llm import OpenAILLMProvider


def _agent() -> AgentProfile:
    return AgentProfile(
        agent_id="default",
        display_name="Test Companion",
        avatar_id="metahuman_default",
        voice_profile_id="uzbek_default",
    )


def _transcript(text: str = "Salom, qalaysan?") -> TranscriptResult:
    return TranscriptResult(text=text, provider_id="test")


def _analysis() -> VoiceAnalysisResult:
    return VoiceAnalysisResult(provider_id="test", status="ok", emotion="attentive")


def _chat_payload(content: object) -> dict[str, Any]:
    body = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return {"choices": [{"message": {"content": body}}]}


class FakeChatClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.calls: list[list[dict[str, str]]] = []

    def create_chat_completion(self, *, api_key: str, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(messages)
        return self.payloads.pop(0)


class OpenAILLMProviderTests(unittest.TestCase):
    def _provider(self, client: FakeChatClient) -> OpenAILLMProvider:
        return OpenAILLMProvider(
            api_key_configured=True,
            api_key_env="OPENAI_API_KEY",
            api_key="sk-test",
            client=client,
        )

    def test_valid_response_parsed(self) -> None:
        client = FakeChatClient(
            [
                _chat_payload(
                    {
                        "response": "Salom! Sizga qanday yordam bera olaman?",
                        "mood": "happy",
                        "behavior": "speak",
                        "speech_style": "brief",
                        "safety_level": "normal",
                    }
                )
            ]
        )
        result = self._provider(client).respond(_transcript(), _analysis(), _agent())
        self.assertEqual(result.mood, "happy")
        self.assertEqual(result.response, "Salom! Sizga qanday yordam bera olaman?")
        self.assertEqual(len(client.calls), 1)

    def test_unknown_enum_values_fall_back_to_defaults(self) -> None:
        client = FakeChatClient(
            [
                _chat_payload(
                    {
                        "response": "Yaxshi.",
                        "mood": "furious",
                        "behavior": "dance",
                        "speech_style": "epic",
                        "safety_level": "unknown",
                    }
                )
            ]
        )
        result = self._provider(client).respond(_transcript(), _analysis(), _agent())
        self.assertEqual(result.mood, "neutral")
        self.assertEqual(result.behavior, "speak")
        self.assertEqual(result.speech_style, "normal")
        self.assertEqual(result.safety_level, "normal")

    def test_repair_retry_after_invalid_json(self) -> None:
        client = FakeChatClient(
            [
                _chat_payload("bu json emas"),
                _chat_payload({"response": "Endi to'g'ri javob.", "mood": "neutral"}),
            ]
        )
        result = self._provider(client).respond(_transcript(), _analysis(), _agent())
        self.assertEqual(result.response, "Endi to'g'ri javob.")
        self.assertEqual(len(client.calls), 2)
        repair_message = client.calls[1][-1]["content"]
        self.assertIn("JSON", repair_message)

    def test_markdown_response_triggers_repair(self) -> None:
        client = FakeChatClient(
            [
                _chat_payload({"response": "```salom```"}),
                _chat_payload({"response": "Salom, xush kelibsiz."}),
            ]
        )
        result = self._provider(client).respond(_transcript(), _analysis(), _agent())
        self.assertEqual(result.response, "Salom, xush kelibsiz.")

    def test_missing_key_raises(self) -> None:
        provider = OpenAILLMProvider(
            api_key_configured=False,
            api_key_env="OPENAI_API_KEY",
        )
        with self.assertRaises(ValueError):
            provider.respond(_transcript(), _analysis(), _agent())

    def test_persona_and_emotion_in_messages(self) -> None:
        client = FakeChatClient([_chat_payload({"response": "Xo'p."})])
        self._provider(client).respond(_transcript(), _analysis(), _agent())
        messages = client.calls[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("o'zbek", messages[0]["content"].lower())
        self.assertIn("attentive", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
