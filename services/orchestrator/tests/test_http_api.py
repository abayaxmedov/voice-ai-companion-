import sys
import base64
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.api.router import LocalApiRouter  # noqa: E402
from companion_core.avatar_bridge import AvatarBridgeClient  # noqa: E402
from companion_core.config import ProviderRuntimeConfig  # noqa: E402
from companion_core.runtime import build_default_runtime  # noqa: E402
from companion_core.serialization import to_jsonable  # noqa: E402


class FakeAvatarBridgeClient(AvatarBridgeClient):
    requested_path = ""

    def _get(self, path):
        self.requested_path = path
        return {
            "running": True,
            "stream_ready": True,
            "avatar_id": "metahuman_default",
            "player_url": "http://127.0.0.1:8888",
            "queued_events": 0,
        }


class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.runtime = build_default_runtime(
            ProviderRuntimeConfig(audio_cache_dir=self._tmp.name)
        )
        self.router = LocalApiRouter(self.runtime)

    def tearDown(self):
        self._tmp.cleanup()

    def test_health(self):
        response = self.router.handle("GET", "/health")
        payload = to_jsonable(response.payload)

        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["service"], "orchestrator")
        self.assertEqual(payload["state"], "idle")
        self.assertEqual(len(payload["providers"]), 4)
        self.assertEqual(payload["selected_providers"]["tts"], "mock_tts")
        self.assertIn("avatar_bridge", payload)

    def test_provider_catalog_exposes_optional_integrations(self):
        response = self.router.handle("GET", "/providers/catalog")
        payload = to_jsonable(response.payload)

        self.assertEqual(response.status, 200)
        provider_ids = {provider["provider_id"] for provider in payload["providers"]}
        self.assertIn("mock_tts", provider_ids)
        self.assertIn("elevenlabs", provider_ids)
        self.assertIn("kokoro", provider_ids)
        self.assertIn("hume", provider_ids)
        self.assertIn("assemblyai", provider_ids)
        self.assertIn("deepgram", provider_ids)

    def test_configured_provider_health_uses_secret_presence_not_secret_value(self):
        runtime = build_default_runtime(
            ProviderRuntimeConfig(
                elevenlabs_api_key_configured=True,
                elevenlabs_api_key="secret-value",
                elevenlabs_voice_id="voice-test",
                hume_api_key_configured=True,
                hume_base_url="https://api.hume.ai",
            )
        )
        router = LocalApiRouter(runtime)
        payload = to_jsonable(router.handle("GET", "/providers/catalog").payload)

        providers = {provider["provider_id"]: provider for provider in payload["providers"]}
        self.assertTrue(providers["elevenlabs"]["ready"])
        self.assertEqual(providers["elevenlabs"]["status"], "configured")
        self.assertTrue(providers["hume"]["ready"])
        self.assertNotIn("voice-test", str(providers["elevenlabs"]))
        self.assertNotIn("secret-value", str(providers["elevenlabs"]))
        self.assertNotIn("secret", str(providers["hume"]).lower())

    def test_voice_turn(self):
        response = self.router.handle(
            "POST",
            "/voice/turn",
            {
                "session_id": "test-session",
                "agent_id": "default",
                "transcript_override": "Bugun ob-havo qanday?",
            },
        )
        payload = to_jsonable(response.payload)

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["session_id"], "test-session")
        self.assertEqual(payload["transcript"]["text"], "Bugun ob-havo qanday?")
        self.assertEqual(payload["analysis"]["status"], "ok")
        self.assertEqual(payload["avatar_job"]["avatar_id"], "metahuman_default")

    def test_audio_upload_returns_local_audio_ref(self):
        response = self.router.handle(
            "POST",
            "/audio/upload",
            {
                "session_id": "test-session",
                "mime_type": "audio/webm",
                "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
            },
        )
        payload = to_jsonable(response.payload)

        self.assertEqual(response.status, 200)
        self.assertTrue(payload["audio_ref"].startswith("file://"))
        self.assertEqual(payload["mime_type"], "audio/webm")
        self.assertEqual(payload["size_bytes"], len(b"fake-audio"))

    def test_audio_upload_rejects_invalid_base64(self):
        response = self.router.handle(
            "POST",
            "/audio/upload",
            {
                "session_id": "test-session",
                "mime_type": "audio/webm",
                "audio_base64": "not valid!",
            },
        )

        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload["error"], "audio_upload_failed")

    def test_cached_audio_endpoint_serves_audio_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "assistant-reply.mp3"
            audio_path.write_bytes(b"mp3 bytes")
            runtime = build_default_runtime(
                ProviderRuntimeConfig(
                    audio_cache_dir=temp_dir,
                    orchestrator_public_base_url="http://test.local",
                )
            )
            router = LocalApiRouter(runtime)

            public_ref = runtime.public_audio_ref(f"file://{audio_path}")
            response = router.handle("GET", "/audio/cache/assistant-reply.mp3")

        self.assertEqual(public_ref, "http://test.local/audio/cache/assistant-reply.mp3")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload, b"mp3 bytes")
        self.assertEqual(response.headers["Content-Type"], "audio/mpeg")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_cached_audio_endpoint_rejects_path_traversal(self):
        response = self.router.handle("GET", "/audio/cache/../secret.mp3")

        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload["error"], "audio_read_failed")

    def test_voice_turn_validation_error(self):
        response = self.router.handle(
            "POST",
            "/voice/turn",
            {"session_id": "test-session", "agent_id": "default"},
        )

        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload["error"], "voice_turn_failed")

    def test_avatar_bridge_health_exposes_player_url(self):
        bridge = FakeAvatarBridgeClient()
        health = to_jsonable(bridge.health())

        self.assertEqual(bridge.requested_path, "/avatar/status")
        self.assertTrue(health["ready"])
        self.assertTrue(health["stream_ready"])
        self.assertEqual(health["bridge_url"], "http://127.0.0.1:8770")
        self.assertEqual(health["player_url"], "http://127.0.0.1:8888")
        self.assertEqual(health["url"], "http://127.0.0.1:8888")


if __name__ == "__main__":
    unittest.main()
