from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class RuntimeState(str, Enum):
    BOOTING = "booting"
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    THINKING = "thinking"
    CONFIRMING = "confirming"
    ACTING = "acting"
    SYNTHESIZING = "synthesizing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class ProviderKind(str, Enum):
    STT = "stt"
    LLM = "llm"
    TTS = "tts"
    VOICE_ANALYSIS = "voice_analysis"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ProviderHealth:
    provider_id: str
    kind: ProviderKind
    ready: bool
    status: str = "unknown"
    latency_ms: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    display_name: str
    avatar_id: str
    voice_profile_id: str
    language: str = "uz-Latn"
    persona: str = "Professional, warm, concise Uzbek voice companion."
    enabled_tools: tuple[str, ...] = ()
    # Personalization (Unclaw-style "vibe" profile). Sliders are 0..1.
    user_name: str = ""
    city: str = ""
    timezone: str = ""
    vibe_formality: float = 0.35
    vibe_humor: float = 0.5
    vibe_directness: float = 0.4
    vibe_verbosity: float = 0.35
    hobbies: tuple[str, ...] = ()


@dataclass(frozen=True)
class VoiceTurnRequest:
    session_id: str
    agent_id: str
    audio_ref: str | None = None
    transcript_override: str | None = None
    interrupt_previous: bool = False
    user_locale: str = "uz-Latn"

    def validate(self) -> None:
        if not self.audio_ref and not self.transcript_override:
            raise ValueError("VoiceTurnRequest requires audio_ref or transcript_override.")


@dataclass(frozen=True)
class AudioUploadResult:
    audio_ref: str
    mime_type: str
    size_bytes: int
    cache_path: str


@dataclass(frozen=True)
class CachedAudioFile:
    filename: str
    mime_type: str
    content: bytes


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str = "uz-Latn"
    confidence: float | None = None
    provider_id: str = "unknown"


@dataclass(frozen=True)
class VoiceAnalysisResult:
    provider_id: str
    status: str
    language: str | None = None
    language_confidence: float | None = None
    sentiment: str | None = None
    emotion: str | None = None
    speaking_rate_wpm: float | None = None
    audio_quality: str | None = None
    warnings: tuple[str, ...] = ()
    raw_summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def unavailable(cls, provider_id: str, reason: str) -> "VoiceAnalysisResult":
        return cls(provider_id=provider_id, status="unavailable", warnings=(reason,))


@dataclass(frozen=True)
class ToolRequest:
    tool_id: str
    params: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    confirmation_prompt: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    response: str
    mood: str = "neutral"
    behavior: str = "speak"
    speech_style: str = "normal"
    action: ToolRequest | None = None
    memory_update: dict[str, Any] | None = None
    safety_level: str = "normal"
    debug_reason: str | None = None

    def validate_for_speech(self) -> None:
        if not self.response.strip():
            raise ValueError("LLMResponse.response cannot be empty.")
        blocked_markers = ("```", "|", "# ")
        if any(marker in self.response for marker in blocked_markers):
            raise ValueError("Spoken response must be plain voice text, not markdown.")


@dataclass(frozen=True)
class TTSResult:
    audio_ref: str
    provider_id: str
    duration_ms: int | None = None
    sample_rate_hz: int | None = None
    timing: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisemeFrame:
    time_ms: int
    name: str
    weight: float


@dataclass(frozen=True)
class AvatarPlaybackJob:
    turn_id: str
    avatar_id: str
    audio_ref: str
    mood: str
    behavior: str
    visemes: tuple[VisemeFrame, ...] = ()
    # Audio-tahlildan olingan og'iz egri chiziqlari (fps + 0..1 massivlar):
    # visemelar QAYSI shaklni, curves QANCHA va QACHON ekanini beradi.
    mouth_curves: dict[str, Any] | None = None
    allow_interrupt: bool = True
    job_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class VoiceTurnResult:
    turn_id: str
    session_id: str
    agent_id: str
    transcript: TranscriptResult
    analysis: VoiceAnalysisResult
    llm_response: LLMResponse
    tts: TTSResult
    avatar_job: AvatarPlaybackJob
    state: RuntimeState = RuntimeState.SPEAKING
    latency_ms: dict[str, int] = field(default_factory=dict)
