from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from companion_core.contracts import TranscriptResult, VoiceAnalysisResult


class HumeAnalysisClient(Protocol):
    def analyze_audio(self, audio_ref: str, transcript: TranscriptResult) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class HumeFixtureClient:
    """Dev-only client that replays a saved Hume-style JSON response."""

    fixture_path: str

    def analyze_audio(self, audio_ref: str, transcript: TranscriptResult) -> dict[str, Any]:
        del audio_ref, transcript
        path = Path(self.fixture_path).expanduser()
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


def hume_result_from_payload(payload: dict[str, Any], transcript: TranscriptResult) -> VoiceAnalysisResult:
    emotions = _extract_emotions(payload)
    if not emotions:
        return VoiceAnalysisResult.unavailable("hume", "Hume response did not include prosody emotions.")

    top_name, top_score = max(emotions, key=lambda item: item[1])
    sentiment = _sentiment_for_emotion(top_name)

    return VoiceAnalysisResult(
        provider_id="hume",
        status="ok",
        language=transcript.language,
        language_confidence=transcript.confidence,
        sentiment=sentiment,
        emotion=_canonical_emotion(top_name),
        speaking_rate_wpm=_extract_number(payload, ("speaking_rate_wpm", "wpm")),
        audio_quality=_extract_audio_quality(payload),
        raw_summary={
            "top_emotion": top_name,
            "top_score": round(top_score, 4),
            "emotions": [
                {"name": name, "score": round(score, 4)}
                for name, score in sorted(emotions, key=lambda item: item[1], reverse=True)[:8]
            ],
        },
    )


def _extract_emotions(payload: Any) -> list[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    _walk_for_emotions(payload, found)
    return found


def _walk_for_emotions(node: Any, found: list[tuple[str, float]]) -> None:
    if isinstance(node, dict):
        emotions = node.get("emotions")
        if isinstance(emotions, list):
            for item in emotions:
                parsed = _parse_emotion(item)
                if parsed:
                    found.append(parsed)
        for value in node.values():
            _walk_for_emotions(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_for_emotions(value, found)


def _parse_emotion(item: Any) -> tuple[str, float] | None:
    if not isinstance(item, dict):
        return None
    raw_name = item.get("name") or item.get("label") or item.get("emotion")
    raw_score = item.get("score") or item.get("probability") or item.get("value")
    if raw_name is None or raw_score is None:
        return None
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None
    name = str(raw_name).strip()
    if not name:
        return None
    return name, max(0.0, min(1.0, score))


def _canonical_emotion(emotion: str) -> str:
    key = emotion.strip().lower().replace(" ", "_")
    aliases = {
        "anger": "angry",
        "anxiety": "anxious",
        "calmness": "calm",
        "concentration": "focused",
        "confusion": "confused",
        "distress": "distressed",
        "excitement": "excited",
        "interest": "interested",
        "joy": "joyful",
        "sadness": "sad",
        "tiredness": "tired",
    }
    return aliases.get(key, key)


def _sentiment_for_emotion(emotion: str) -> str:
    key = _canonical_emotion(emotion)
    if key in {"joyful", "excited", "amusement", "adoration", "satisfaction", "pride"}:
        return "positive"
    if key in {
        "angry",
        "anxious",
        "distressed",
        "sad",
        "fear",
        "horror",
        "pain",
        "disappointment",
        "annoyance",
    }:
        return "negative"
    return "neutral"


def _extract_number(payload: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                try:
                    return float(payload[key])
                except (TypeError, ValueError):
                    return None
        for value in payload.values():
            found = _extract_number(value, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _extract_number(value, keys)
            if found is not None:
                return found
    return None


def _extract_audio_quality(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("audio_quality", "quality"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = _extract_audio_quality(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _extract_audio_quality(value)
            if found:
                return found
    return None


def avatar_mood_from_emotion(default_mood: str, analysis: VoiceAnalysisResult) -> str:
    emotion = (analysis.emotion or "").lower()
    if analysis.status != "ok" or not emotion:
        return default_mood
    if emotion in {"angry", "anxious", "distressed", "fear", "horror", "pain", "annoyance"}:
        return "reassuring"
    if emotion in {"sad", "disappointment", "tired"}:
        return "empathetic"
    if emotion in {"joyful", "excited", "amusement", "adoration", "satisfaction", "pride"}:
        return "warm"
    if emotion in {"confused", "doubt"}:
        return "clarifying"
    if emotion in {"focused", "interested", "calm"}:
        return "attentive"
    return default_mood
