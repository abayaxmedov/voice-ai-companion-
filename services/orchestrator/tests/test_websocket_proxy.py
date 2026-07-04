import socket
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.api.websocket_proxy import (  # noqa: E402
    read_ws_frame,
    send_ws_frame,
    websocket_accept_key,
)


class WebSocketProxyTests(unittest.TestCase):
    def test_websocket_accept_key_matches_rfc_example(self):
        self.assertEqual(
            websocket_accept_key("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )

    def test_frame_roundtrip_supports_masked_text(self):
        left, right = socket.socketpair()
        try:
            send_ws_frame(left, 0x1, b'{"type":"audio_input"}', mask=True)
            frame = read_ws_frame(right)
        finally:
            left.close()
            right.close()

        self.assertEqual(frame.opcode, 0x1)
        self.assertEqual(frame.payload, b'{"type":"audio_input"}')


if __name__ == "__main__":
    unittest.main()
