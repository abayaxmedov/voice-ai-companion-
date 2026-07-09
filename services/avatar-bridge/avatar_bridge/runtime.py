from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any
from uuid import uuid4

from avatar_bridge.events import AvatarEvent, AvatarEventType, AvatarRuntimeStatus


@dataclass
class MetaHumanBridgeRuntime:
    """Local event bridge for Unreal/MetaHuman runtime.

    The bridge is useful before Unreal is connected: it queues outgoing events
    and exposes them through HTTP. The real Unreal receiver can poll or subscribe
    to these events in the next integration step.
    """

    avatar_id: str = "metahuman_default"
    player_url: str = "http://127.0.0.1:8888"
    stream_ready: bool = False
    _events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=200))
    _errors: deque[str] = field(default_factory=lambda: deque(maxlen=20))
    _last_event_type: str | None = None

    def status(self) -> AvatarRuntimeStatus:
        return AvatarRuntimeStatus(
            running=True,
            stream_ready=self.stream_ready,
            avatar_id=self.avatar_id,
            player_url=self.player_url,
            last_event_type=self._last_event_type,
            queued_events=len(self._events),
            errors=tuple(self._errors),
        )

    def mark_ready(self, avatar_id: str | None = None, player_url: str | None = None) -> dict[str, Any]:
        # UE yangi ulandi — undan oldin yig'ilib qolgan eski avatar.play
        # hodisalari birdan replay bo'lmasligi uchun navbatni tozalaymiz.
        self._events.clear()
        if avatar_id:
            self.avatar_id = avatar_id
        if player_url:
            self.player_url = player_url
        self.stream_ready = True
        return self.push(
            AvatarEvent(
                event_type=AvatarEventType.READY,
                payload={"avatar_id": self.avatar_id, "player_url": self.player_url},
            )
        )

    def set_state(self, state: str) -> dict[str, Any]:
        return self.push(
            AvatarEvent(
                event_type=AvatarEventType.STATE,
                payload={"avatar_id": self.avatar_id, "state": state},
            )
        )

    def play(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload.setdefault("avatar_id", self.avatar_id)
        return self.push(AvatarEvent(event_type=AvatarEventType.PLAY, payload=payload))

    def sync(self, position_ms: float, turn_id: str | None = None) -> dict[str, Any]:
        """Electron'dagi haqiqiy audio pozitsiyasi — UE lab-sinxron soatini
        shu qiymatga tuzatadi (hodisa created_at'i bilan latency kompensatsiyasi)."""
        return self.push(
            AvatarEvent(
                event_type=AvatarEventType.SYNC,
                payload={
                    "avatar_id": self.avatar_id,
                    "turn_id": turn_id,
                    "position_ms": float(position_ms),
                },
            )
        )

    def interrupt(self, turn_id: str | None = None, reason: str = "user_barge_in") -> dict[str, Any]:
        return self.push(
            AvatarEvent(
                event_type=AvatarEventType.INTERRUPT,
                payload={"turn_id": turn_id, "reason": reason},
            )
        )

    def next_events(self, limit: int = 25) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for _ in range(min(limit, len(self._events))):
            events.append(self._events.popleft())
        return events

    def recent_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def push(self, event: AvatarEvent) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "type": event.event_type.value,
            "payload": event.payload,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._last_event_type = event.event_type.value
        self._events.append(record)
        return record

