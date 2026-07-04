"""Phoneme-accurate viseme timeline for Uzbek (Latin) speech.

Two sources, best first:
1. ElevenLabs character alignment (real per-character timestamps) when the TTS
   provider stored it in ``TTSResult.timing["alignment"]``.
2. Grapheme-to-viseme fallback: Uzbek orthography is close to phonemic, so the
   response text itself yields the viseme *sequence*; timing is distributed by
   per-phoneme durations and scaled to the synthesized audio duration.

Viseme names follow the Oculus/ARKit lip-sync convention understood by the
renderer: sil PP FF DD kk CH SS nn RR aa E I O U.
"""

from __future__ import annotations

from companion_core.contracts import VisemeFrame

# Apostrophe look-alikes used in Uzbek Latin text (oʻ gʻ and tutuq belgisi).
_APOSTROPHES = "'‘’ʻʼ`´"

# Digraphs must win over single letters: sh, ch, ng, o', g'.
_DIGRAPH_VISEMES = {
    "sh": ("CH", 0.75, 90),
    "ch": ("CH", 0.78, 90),
    "ng": ("kk", 0.50, 70),
}
_APOSTROPHE_DIGRAPH_VISEMES = {
    "o": ("O", 0.90, 120),  # oʻ
    "g": ("kk", 0.55, 70),  # gʻ
}

# letter -> (viseme, weight, base duration ms)
_LETTER_VISEMES = {
    "a": ("aa", 0.95, 120),
    "o": ("O", 0.88, 120),
    "e": ("E", 0.80, 115),
    "i": ("I", 0.80, 105),
    "u": ("U", 0.85, 110),
    "b": ("PP", 0.95, 75),
    "p": ("PP", 0.95, 75),
    "m": ("PP", 0.90, 80),
    "f": ("FF", 0.70, 70),
    "v": ("FF", 0.65, 65),
    "s": ("SS", 0.65, 85),
    "z": ("SS", 0.60, 75),
    "j": ("CH", 0.75, 85),
    "x": ("kk", 0.50, 75),
    "h": ("kk", 0.40, 60),
    "k": ("kk", 0.55, 70),
    "g": ("kk", 0.55, 65),
    "q": ("kk", 0.55, 75),
    "t": ("DD", 0.55, 60),
    "d": ("DD", 0.55, 60),
    "n": ("nn", 0.50, 60),
    "l": ("nn", 0.50, 65),
    "r": ("RR", 0.55, 65),
    "y": ("I", 0.45, 55),
    "w": ("U", 0.60, 65),
    "c": ("SS", 0.60, 75),
}

_WORD_GAP = ("sil", 0.0, 80)
_PAUSE_PUNCT = {",": 150, ";": 170, ":": 170, "—": 200, "-": 60}
_STOP_PUNCT = {".": 240, "!": 240, "?": 240, "…": 280}

_MIN_FRAME_MS = 25
_MAX_FRAMES = 400


def _phoneme_units(text: str) -> list[tuple[str, float, int]]:
    """Map normalized Uzbek Latin text to (viseme, weight, base_ms) units."""
    lower = text.lower()
    units: list[tuple[str, float, int]] = []
    i = 0
    n = len(lower)
    while i < n:
        ch = lower[i]
        nxt = lower[i + 1] if i + 1 < n else ""
        pair = ch + nxt
        if pair in _DIGRAPH_VISEMES:
            units.append(_DIGRAPH_VISEMES[pair])
            i += 2
            continue
        if ch in _APOSTROPHE_DIGRAPH_VISEMES and nxt in _APOSTROPHES:
            units.append(_APOSTROPHE_DIGRAPH_VISEMES[ch])
            i += 2
            continue
        if ch in _LETTER_VISEMES:
            units.append(_LETTER_VISEMES[ch])
        elif ch.isspace():
            if units and units[-1][0] != "sil":
                units.append(_WORD_GAP)
        elif ch in _STOP_PUNCT:
            units.append(("sil", 0.0, _STOP_PUNCT[ch]))
        elif ch in _PAUSE_PUNCT:
            units.append(("sil", 0.0, _PAUSE_PUNCT[ch]))
        # Tutuq belgisi, digits (already normalized) and unknowns are skipped.
        i += 1
    return units


def _merge_frames(frames: list[VisemeFrame]) -> list[VisemeFrame]:
    merged: list[VisemeFrame] = []
    for frame in frames:
        if merged and merged[-1].name == frame.name:
            continue
        if merged and frame.time_ms - merged[-1].time_ms < _MIN_FRAME_MS:
            merged[-1] = VisemeFrame(
                time_ms=merged[-1].time_ms,
                name=frame.name,
                weight=max(merged[-1].weight, frame.weight),
            )
            continue
        merged.append(frame)
    return merged[:_MAX_FRAMES]


def visemes_from_text(text: str, duration_ms: int | None) -> tuple[VisemeFrame, ...]:
    """Fallback path: sequence from graphemes, timing scaled to audio length."""
    units = _phoneme_units(text)
    if not units:
        return ()
    natural_ms = sum(base for _, _, base in units)
    if natural_ms <= 0:
        return ()
    scale = 1.0
    if duration_ms and duration_ms > 0:
        scale = max(0.5, min(2.0, duration_ms / natural_ms))

    frames: list[VisemeFrame] = []
    cursor = 0.0
    for name, weight, base in units:
        frames.append(VisemeFrame(time_ms=int(cursor), name=name, weight=weight))
        cursor += base * scale
    frames.append(VisemeFrame(time_ms=int(cursor), name="sil", weight=0.0))
    return tuple(_merge_frames(frames))


def visemes_from_alignment(alignment: dict) -> tuple[VisemeFrame, ...]:
    """Precise path: ElevenLabs character-level timestamps."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not chars or len(chars) != len(starts) or len(chars) != len(ends):
        return ()

    frames: list[VisemeFrame] = []
    last_end_ms = 0.0
    i = 0
    n = len(chars)
    while i < n:
        ch = str(chars[i]).lower()
        nxt = str(chars[i + 1]).lower() if i + 1 < n else ""
        start_ms = float(starts[i]) * 1000.0
        end_ms = float(ends[i]) * 1000.0
        consumed = 1

        unit: tuple[str, float, int] | None = None
        if len(ch) == 1:
            pair = ch + nxt
            if pair in _DIGRAPH_VISEMES:
                unit = _DIGRAPH_VISEMES[pair]
                end_ms = float(ends[i + 1]) * 1000.0
                consumed = 2
            elif ch in _APOSTROPHE_DIGRAPH_VISEMES and nxt and nxt in _APOSTROPHES:
                unit = _APOSTROPHE_DIGRAPH_VISEMES[ch]
                end_ms = float(ends[i + 1]) * 1000.0
                consumed = 2
            elif ch in _LETTER_VISEMES:
                unit = _LETTER_VISEMES[ch]

        if unit is not None:
            # Insert silence for real pauses between characters.
            if frames and start_ms - last_end_ms > 140:
                frames.append(
                    VisemeFrame(time_ms=int(last_end_ms), name="sil", weight=0.0)
                )
            frames.append(
                VisemeFrame(time_ms=int(start_ms), name=unit[0], weight=unit[1])
            )
            last_end_ms = end_ms
        elif ch.isspace() or ch in _STOP_PUNCT or ch in _PAUSE_PUNCT:
            if frames and frames[-1].name != "sil":
                frames.append(
                    VisemeFrame(time_ms=int(max(start_ms, last_end_ms)), name="sil", weight=0.0)
                )
        i += consumed

    if frames and frames[-1].name != "sil":
        frames.append(VisemeFrame(time_ms=int(last_end_ms), name="sil", weight=0.0))
    return tuple(_merge_frames(frames))


def generate_viseme_timeline(
    text: str,
    duration_ms: int | None,
    alignment: dict | None = None,
) -> tuple[VisemeFrame, ...]:
    """Best-effort phoneme-accurate timeline (alignment first, text fallback)."""
    if alignment:
        frames = visemes_from_alignment(alignment)
        if len(frames) >= 2:
            return frames
    return visemes_from_text(text, duration_ms)
