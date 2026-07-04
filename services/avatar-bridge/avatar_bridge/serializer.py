from __future__ import annotations

import json

from avatar_bridge.events import AvatarEvent


def serialize_event(event: AvatarEvent) -> str:
    return json.dumps(
        {"type": event.event_type.value, "payload": event.payload},
        ensure_ascii=False,
        separators=(",", ":"),
    )

