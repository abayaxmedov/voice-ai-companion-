from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import threading
from urllib.parse import urlencode, urlparse

from companion_core.config import ProviderRuntimeConfig


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


@dataclass(frozen=True)
class WebSocketFrame:
    opcode: int
    payload: bytes


class HumeEviWebSocketProxy:
    def __init__(self, config: ProviderRuntimeConfig) -> None:
        self._config = config

    def serve(self, client_socket: socket.socket) -> None:
        if not self._config.hume_api_key:
            _send_text(client_socket, {"type": "error", "message": "HUME_API_KEY is not configured."})
            _send_close(client_socket)
            return
        if not self._config.hume_evi_config_id:
            _send_text(
                client_socket,
                {"type": "error", "message": "HUME_EVI_CONFIG_ID is not configured."},
            )
            _send_close(client_socket)
            return

        hume_socket: socket.socket | None = None
        stop_event = threading.Event()
        try:
            hume_socket = connect_hume_evi(self._config)
            _send_text(client_socket, {"type": "proxy_status", "status": "connected"})

            to_hume = threading.Thread(
                target=_forward_browser_to_hume,
                args=(client_socket, hume_socket, stop_event),
                daemon=True,
            )
            to_browser = threading.Thread(
                target=_forward_hume_to_browser,
                args=(hume_socket, client_socket, stop_event),
                daemon=True,
            )
            to_hume.start()
            to_browser.start()
            while not stop_event.wait(0.1):
                if not to_hume.is_alive() or not to_browser.is_alive():
                    break
        except Exception as exc:  # noqa: BLE001 - websocket boundary returns safe error.
            try:
                _send_text(client_socket, {"type": "error", "message": f"Hume EVI connection failed: {exc}"})
            except OSError:
                pass
        finally:
            stop_event.set()
            if hume_socket is not None:
                _safe_shutdown(hume_socket)
            _safe_shutdown(client_socket)


def websocket_accept_key(client_key: str) -> str:
    digest = hashlib.sha1(f"{client_key}{WEBSOCKET_GUID}".encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def connect_hume_evi(config: ProviderRuntimeConfig) -> socket.socket:
    url = _hume_ws_url(config)
    parsed = urlparse(url)
    if parsed.scheme != "wss":
        raise ValueError("Hume EVI websocket URL must use wss://")

    port = parsed.port or 443
    raw_socket = socket.create_connection((parsed.hostname or "", port), timeout=15)
    tls_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=parsed.hostname)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {parsed.hostname}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    tls_socket.sendall(request.encode("ascii"))
    response = _read_http_headers(tls_socket)
    if " 101 " not in response.split("\r\n", 1)[0]:
        raise RuntimeError(_safe_handshake_error(response))
    return tls_socket


def _hume_ws_url(config: ProviderRuntimeConfig) -> str:
    base_url = config.hume_evi_ws_url.rstrip("?")
    query = {
        "api_key": config.hume_api_key,
        "config_id": config.hume_evi_config_id,
        "verbose_transcription": "true",
    }
    return f"{base_url}?{urlencode(query)}"


def _forward_browser_to_hume(
    client_socket: socket.socket,
    hume_socket: socket.socket,
    stop_event: threading.Event,
) -> None:
    try:
        while not stop_event.is_set():
            frame = read_ws_frame(client_socket)
            if frame.opcode == 0x8:
                send_ws_frame(hume_socket, 0x8, frame.payload, mask=True)
                stop_event.set()
                return
            if frame.opcode == 0x9:
                send_ws_frame(client_socket, 0xA, frame.payload)
                continue
            if frame.opcode in {0x1, 0x2, 0x0}:
                send_ws_frame(hume_socket, frame.opcode, frame.payload, mask=True)
    except (ConnectionError, EOFError, OSError):
        stop_event.set()


def _forward_hume_to_browser(
    hume_socket: socket.socket,
    client_socket: socket.socket,
    stop_event: threading.Event,
) -> None:
    try:
        while not stop_event.is_set():
            frame = read_ws_frame(hume_socket)
            if frame.opcode == 0x8:
                send_ws_frame(client_socket, 0x8, frame.payload)
                stop_event.set()
                return
            if frame.opcode == 0x9:
                send_ws_frame(hume_socket, 0xA, frame.payload, mask=True)
                continue
            if frame.opcode in {0x1, 0x2, 0x0}:
                send_ws_frame(client_socket, frame.opcode, frame.payload)
    except (ConnectionError, EOFError, OSError):
        stop_event.set()


def read_ws_frame(sock: socket.socket) -> WebSocketFrame:
    header = _recv_exact(sock, 2)
    first, second = header
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask_key = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
    return WebSocketFrame(opcode=opcode, payload=payload)


def send_ws_frame(sock: socket.socket, opcode: int, payload: bytes, mask: bool = False) -> None:
    first = 0x80 | (opcode & 0x0F)
    length = len(payload)
    if length < 126:
        header = bytes([first, length | (0x80 if mask else 0)])
    elif length <= 0xFFFF:
        header = bytes([first, 126 | (0x80 if mask else 0)]) + struct.pack("!H", length)
    else:
        header = bytes([first, 127 | (0x80 if mask else 0)]) + struct.pack("!Q", length)
    if mask:
        mask_key = os.urandom(4)
        payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        sock.sendall(header + mask_key + payload)
        return
    sock.sendall(header + payload)


def _send_text(sock: socket.socket, payload: dict[str, object]) -> None:
    send_ws_frame(sock, 0x1, json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _send_close(sock: socket.socket) -> None:
    send_ws_frame(sock, 0x8, b"")


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("WebSocket connection closed.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_http_headers(sock: socket.socket) -> str:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if len(data) > 65536:
            break
    return data.decode("utf-8", errors="replace")


def _safe_handshake_error(response: str) -> str:
    status_line = response.split("\r\n", 1)[0].strip()
    return f"Hume EVI websocket handshake failed: {status_line or 'no response'}"


def _safe_shutdown(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass
