from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from avatar_bridge.runtime import MetaHumanBridgeRuntime


class MetaHumanBridgeRouter:
    def __init__(self, runtime: MetaHumanBridgeRuntime) -> None:
        self._runtime = runtime

    def handle(self, method: str, path: str, payload: dict[str, Any] | None = None, query: str = ""):
        method = method.upper()
        payload = payload or {}
        if method == "GET" and path == "/avatar/status":
            return 200, self._runtime.status()
        if method == "GET" and path == "/avatar/events":
            params = parse_qs(query)
            mode = params.get("mode", ["recent"])[0]
            if mode == "poll":
                return 200, {"events": self._runtime.next_events()}
            return 200, {"events": self._runtime.recent_events()}
        if method == "POST" and path == "/avatar/ready":
            return 200, self._runtime.mark_ready(payload.get("avatar_id"), payload.get("player_url"))
        if method == "POST" and path == "/avatar/state":
            return 200, self._runtime.set_state(str(payload.get("state", "idle")))
        if method == "POST" and path == "/avatar/play":
            return 200, self._runtime.play(payload)
        if method == "POST" and path == "/avatar/interrupt":
            return 200, self._runtime.interrupt(payload.get("turn_id"), payload.get("reason", "user_barge_in"))
        return 404, {"error": "not_found", "path": path}


def create_handler(runtime: MetaHumanBridgeRuntime):
    router = MetaHumanBridgeRouter(runtime)

    class AvatarBridgeRequestHandler(BaseHTTPRequestHandler):
        server_version = "MetaHumanBridge/0.1"

        def do_OPTIONS(self) -> None:
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            status, payload = router.handle("GET", parsed.path, query=parsed.query)
            self._send_json(payload, status=status)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            status, payload = router.handle("POST", parsed.path, self._read_json())
            self._send_json(payload, status=status)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(_to_jsonable(payload), ensure_ascii=False).encode("utf-8")
            origin = self.headers.get("Origin", "")
            allowed_origin = "*"
            if origin.startswith(("http://127.0.0.1", "http://localhost")):
                allowed_origin = origin
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

    return AvatarBridgeRequestHandler


def run_server(runtime: MetaHumanBridgeRuntime, host: str = "127.0.0.1", port: int = 8770) -> None:
    server = ThreadingHTTPServer((host, port), create_handler(runtime))
    print(f"MetaHuman bridge listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _to_jsonable(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value

