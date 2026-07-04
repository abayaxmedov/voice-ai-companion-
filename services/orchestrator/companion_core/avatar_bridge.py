from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from companion_core.contracts import AvatarPlaybackJob
from companion_core.serialization import to_jsonable


@dataclass(frozen=True)
class AvatarBridgeHealth:
    ready: bool
    url: str
    status: str
    bridge_url: str | None = None
    player_url: str | None = None
    stream_ready: bool = False
    avatar_id: str | None = None
    queued_events: int | None = None
    message: str | None = None


class AvatarBridgeClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8770", timeout_s: float = 1.2) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def health(self) -> AvatarBridgeHealth:
        try:
            payload = self._get("/avatar/status")
        except Exception as exc:  # noqa: BLE001 - bridge is optional during dev.
            return AvatarBridgeHealth(
                ready=False,
                url=self.base_url,
                status="unreachable",
                bridge_url=self.base_url,
                message=str(exc),
            )
        player_url = str(payload.get("player_url") or "")
        return AvatarBridgeHealth(
            ready=True,
            url=player_url or self.base_url,
            status="connected",
            bridge_url=self.base_url,
            player_url=player_url or None,
            stream_ready=bool(payload.get("stream_ready", False)),
            avatar_id=payload.get("avatar_id"),
            queued_events=payload.get("queued_events"),
        )

    def send_playback(self, job: AvatarPlaybackJob) -> dict[str, Any]:
        payload = to_jsonable(job)
        return self._post("/avatar/play", payload)

    def _get(self, path: str) -> dict[str, Any]:
        with urlopen(f"{self.base_url}{path}", timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except URLError:
            raise
