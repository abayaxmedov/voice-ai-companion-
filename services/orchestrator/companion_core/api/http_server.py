from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from companion_core.api.router import LocalApiRouter
from companion_core.api.websocket_proxy import HumeEviWebSocketProxy, websocket_accept_key
from companion_core.contracts import VoiceTurnRequest
from companion_core.pipeline.voice_turn import StreamingUnsupported
from companion_core.runtime import RuntimeContext
from companion_core.serialization import to_jsonable


# Qimmat/o'zgartiruvchi endpointlar: ochiq portda token talab qilinadi
# (COMPANION_API_TOKEN o'rnatilgan bo'lsa). Statik UI va /health ochiq qoladi.
_PROTECTED_POST_PATHS = {
    "/voice/turn",
    "/voice/turn/stream",
    "/audio/upload",
    "/conversation/clear",
}
_PROTECTED_MUTATION_PATHS = {"/settings", "/profile"}


def _api_token() -> str:
    token = os.environ.get("COMPANION_API_TOKEN", "").strip()
    if token:
        return token
    # .env faylidan ham o'qiymiz (server deploy .env ga yozadi).
    try:
        from companion_core.config import _default_env_path

        env_path = _default_env_path()
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("COMPANION_API_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except Exception:  # noqa: BLE001 - token ixtiyoriy.
        pass
    return ""


def create_handler(runtime: RuntimeContext):
    router = LocalApiRouter(runtime)
    api_token = _api_token()

    class CompanionRequestHandler(BaseHTTPRequestHandler):
        server_version = "CompanionOrchestrator/0.1"

        def _needs_token(self, method: str, path: str) -> bool:
            if not api_token:
                return False
            if method == "POST" and path in _PROTECTED_POST_PATHS:
                return True
            if method in {"PATCH", "POST", "DELETE"} and path in _PROTECTED_MUTATION_PATHS:
                return True
            if method == "DELETE" and path == "/conversation/clear":
                return True
            return False

        def _authorized(self, method: str, path: str) -> bool:
            if not self._needs_token(method, path):
                return True
            supplied = self.headers.get("X-Companion-Token", "").strip()
            if not supplied:
                query = parse_qs(urlparse(self.path).query)
                supplied = (query.get("token") or [""])[0].strip()
            return bool(supplied) and hmac.compare_digest(supplied, api_token)

        def _reject_unauthorized(self) -> None:
            self._send_json(
                {
                    "error": "unauthorized",
                    "message": "COMPANION_API_TOKEN talab qilinadi (X-Companion-Token yoki ?token=).",
                },
                status=401,
            )

        def do_OPTIONS(self) -> None:
            self._send_json({"ok": True})

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/voice/hume-evi/ws":
                self._handle_hume_evi_websocket()
                return
            response = router.handle("GET", path)
            self._send_response(response)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if not self._authorized("POST", path):
                self._reject_unauthorized()
                return
            if path == "/voice/turn/stream":
                self._handle_voice_turn_stream()
                return
            response = router.handle("POST", path, self._read_json())
            self._send_response(response)

        def _handle_voice_turn_stream(self) -> None:
            """NDJSON chunked oqim: meta -> audio* -> end (past kechikish)."""
            payload = self._read_json()
            try:
                turn_request = VoiceTurnRequest(
                    session_id=str(payload.get("session_id", "dev-session")),
                    agent_id=str(payload.get("agent_id", "default")),
                    audio_ref=payload.get("audio_ref"),
                    transcript_override=payload.get("transcript_override"),
                    interrupt_previous=bool(payload.get("interrupt_previous", False)),
                    user_locale=str(payload.get("user_locale", "uz-Latn")),
                )
                turn_request.validate()
            except Exception as exc:  # noqa: BLE001 - API chegarasi.
                self._send_json(
                    {"error": "invalid_request", "message": str(exc)}, status=400
                )
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-store")
            self._send_common_headers()
            self.end_headers()

            def emit(event) -> None:
                data = (
                    json.dumps(to_jsonable(event), ensure_ascii=False) + "\n"
                ).encode("utf-8")
                self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
                self.wfile.write(data)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

            try:
                runtime.run_voice_turn_stream(turn_request, emit)
            except StreamingUnsupported as exc:
                self._safe_emit(emit, {"type": "error", "error": "stream_unsupported", "message": str(exc)})
            except BrokenPipeError:
                return  # klient uzildi (barge-in) — normal holat
            except Exception as exc:  # noqa: BLE001 - oqim ichida xavfsiz xato.
                self._safe_emit(emit, {"type": "error", "error": "stream_failed", "message": str(exc)})
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError:
                pass

        @staticmethod
        def _safe_emit(emit, event) -> None:
            try:
                emit(event)
            except OSError:
                pass

        def do_PATCH(self) -> None:
            path = urlparse(self.path).path
            if not self._authorized("PATCH", path):
                self._reject_unauthorized()
                return
            response = router.handle("PATCH", path, self._read_json())
            self._send_response(response)

        def do_DELETE(self) -> None:
            path = urlparse(self.path).path
            if not self._authorized("DELETE", path):
                self._reject_unauthorized()
                return
            response = router.handle("DELETE", path)
            self._send_response(response)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_response(self, response) -> None:
            if isinstance(response.payload, bytes):
                self._send_binary(
                    response.payload,
                    status=response.status,
                    headers=response.headers,
                )
                return
            self._send_json(response.payload, status=response.status, headers=response.headers)

        def _send_json(
            self,
            payload: Any,
            status: int = 200,
            headers: dict[str, str] | None = None,
        ) -> None:
            body = json.dumps(to_jsonable(payload), ensure_ascii=False).encode("utf-8")
            headers = headers or {}
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_common_headers()
            if headers:
                for name, value in headers.items():
                    if name.lower() not in {"content-type", "content-length"}:
                        self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_binary(
            self,
            body: bytes,
            status: int = 200,
            headers: dict[str, str] | None = None,
        ) -> None:
            headers = headers or {}
            self.send_response(status)
            self.send_header(
                "Content-Type",
                headers.get("Content-Type", "application/octet-stream"),
            )
            self.send_header("Content-Length", str(len(body)))
            self._send_common_headers()
            for name, value in headers.items():
                if name.lower() not in {"content-type", "content-length"}:
                    self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_common_headers(self) -> None:
            origin = self.headers.get("Origin", "")
            allowed_origin = "*"
            if origin.startswith(("http://127.0.0.1", "http://localhost")):
                allowed_origin = origin
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _handle_hume_evi_websocket(self) -> None:
            client_key = self.headers.get("Sec-WebSocket-Key", "")
            if self.headers.get("Upgrade", "").lower() != "websocket" or not client_key:
                self._send_json(
                    {"error": "websocket_required", "message": "Use WebSocket for Hume EVI."},
                    status=400,
                )
                return
            accept_key = websocket_accept_key(client_key)
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                "\r\n"
            )
            self.connection.sendall(response.encode("ascii"))
            HumeEviWebSocketProxy(runtime.config).serve(self.connection)

    return CompanionRequestHandler


def run_server(runtime: RuntimeContext, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), create_handler(runtime))
    print(f"Companion orchestrator listening on http://{host}:{port}", flush=True)
    server.serve_forever()
