"""Uzbek speech normalization for TTS input.

TZ 12.1: numbers, times, URLs and markdown must be converted to speakable
Uzbek Latin text before the response is sent to any TTS provider.
"""

from __future__ import annotations

import re

_UNITS = {
    0: "nol",
    1: "bir",
    2: "ikki",
    3: "uch",
    4: "to'rt",
    5: "besh",
    6: "olti",
    7: "yetti",
    8: "sakkiz",
    9: "to'qqiz",
}

_TENS = {
    1: "o'n",
    2: "yigirma",
    3: "o'ttiz",
    4: "qirq",
    5: "ellik",
    6: "oltmish",
    7: "yetmish",
    8: "sakson",
    9: "to'qson",
}

_SCALES = (
    (1_000_000_000, "milliard"),
    (1_000_000, "million"),
    (1_000, "ming"),
)


def number_to_uzbek(value: int) -> str:
    """Convert a non-negative integer to Uzbek Latin words."""
    if value < 0:
        return "minus " + number_to_uzbek(-value)
    if value < 10:
        return _UNITS[value]

    parts: list[str] = []
    remainder = value
    for scale, name in _SCALES:
        if remainder >= scale:
            count = remainder // scale
            remainder %= scale
            parts.append(f"{_under_thousand(count)} {name}")
    if remainder:
        parts.append(_under_thousand(remainder))
    return " ".join(parts)


def _under_thousand(value: int) -> str:
    parts: list[str] = []
    hundreds, rest = divmod(value, 100)
    if hundreds:
        prefix = "" if hundreds == 1 else f"{_UNITS[hundreds]} "
        parts.append(f"{prefix}yuz")
    tens, units = divmod(rest, 10)
    if tens:
        parts.append(_TENS[tens])
    if units or (not parts and not hundreds):
        parts.append(_UNITS[units])
    return " ".join(parts)


def time_to_uzbek(hour: int, minute: int) -> str:
    """9:30 -> "to'qqiz yarim"; 9:00 -> "soat to'qqiz"; 9:35 -> "to'qqizu o'ttiz besh daqiqa"."""
    hour_words = number_to_uzbek(hour)
    if minute == 0:
        return f"soat {hour_words}"
    if minute == 30:
        return f"{hour_words} yarim"
    return f"{hour_words}u {number_to_uzbek(minute)} daqiqa"


_MARKDOWN_PATTERNS = (
    (re.compile(r"```.*?```", re.DOTALL), " "),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"\*\*([^*]*)\*\*"), r"\1"),
    (re.compile(r"\*([^*]*)\*"), r"\1"),
    (re.compile(r"__([^_]*)__"), r"\1"),
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),
    (re.compile(r"^\s*[-•]\s+", re.MULTILINE), ""),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\|"), " "),
    # Qolgan yakka markdown belgilari nutqda aytilmaydi.
    (re.compile(r"[#_~>]"), " "),
)

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_PERCENT_RE = re.compile(r"\b(\d+)\s*%")
_DECIMAL_RE = re.compile(r"\b(\d+)[.,](\d+)\b")
_THOUSANDS_RE = re.compile(r"\b(\d{1,3}(?:[ \u00a0](?:\d{3}))+)\b")
_INTEGER_RE = re.compile(r"\b\d+\b")
_URL_RE = re.compile(r"https?://(?:www\.)?([\w.-]+)\S*")
_WWW_RE = re.compile(r"\bwww\.([\w.-]+)\S*")


def normalize_speech_text(text: str) -> str:
    """Normalize an Uzbek assistant response into plain speakable text."""
    result = text

    for pattern, replacement in _MARKDOWN_PATTERNS:
        result = pattern.sub(replacement, result)

    result = _URL_RE.sub(lambda m: _speakable_domain(m.group(1)), result)
    result = _WWW_RE.sub(lambda m: _speakable_domain(m.group(1)), result)
    result = _TIME_RE.sub(lambda m: time_to_uzbek(int(m.group(1)), int(m.group(2))), result)
    result = _PERCENT_RE.sub(lambda m: f"{number_to_uzbek(int(m.group(1)))} foiz", result)
    result = _DECIMAL_RE.sub(
        lambda m: f"{number_to_uzbek(int(m.group(1)))} butun {number_to_uzbek(int(m.group(2)))}",
        result,
    )
    result = _THOUSANDS_RE.sub(
        lambda m: number_to_uzbek(int(m.group(1).replace(" ", "").replace("\u00a0", ""))),
        result,
    )
    result = _INTEGER_RE.sub(lambda m: number_to_uzbek(int(m.group(0))), result)

    return " ".join(result.split())


def _speakable_domain(domain: str) -> str:
    return domain.replace(".", " nuqta ")
