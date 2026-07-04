from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AvatarEventType(str, Enum):
    READY = "avatar.ready"
    STATE = "avatar.state"
    PLAY = "avatar.play"
    INTERRUPT = "avatar.interrupt"
    COMPLETED = "avatar.completed"
    ERROR = "avatar.error"
    SWITCH = "avatar.switch"


@dataclass(frozen=True)
class AvatarEvent:
    event_type: AvatarEventType
    payload: dict[str, Any]


@dataclass(frozen=True)
class AvatarRuntimeStatus:
    running: bool
    stream_ready: bool
    avatar_id: str | None = None
    player_url: str | None = None
    last_event_type: str | None = None
    queued_events: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)
