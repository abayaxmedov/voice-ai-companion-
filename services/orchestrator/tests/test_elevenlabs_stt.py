import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.providers.stt import (  # noqa: E402
    ElevenLabsSTTProvider,
    _elevenlabs_stt_http_error_message,
)


class FakeElevenLabsSTTClient:
    def __init__(self, payload=None):
        self.payload = payload or {
            "text": "Salom, meni eshityapsanmi?",
            "language_code": "uz",
            "language_probability": 0.91,
        }
        self.calls = []

    def create_transcript(self, *, api_key, model_id, audio_path, language_code):
        self.calls.append(
            {
                "api_key": api_key,
                "model_id": model_id,
                "audio_path": audio_path,
                "language_code": language_code,
            }
        )
        return self.payload


class ElevenLabsSTTTests(unittest.TestCase):
    def test_transcribe_local_audio_file(self):
        fake_client = FakeElevenLabsSTTClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "turn.webm"
            audio_path.write_bytes(b"fake-audio")
            provider = ElevenLabsSTTProvider(
                api_key_configured=True,
                api_key_env="ELEVENLABS_API_KEY",
                api_key="test-secret",
                model_id="scribe_v2",
                language_code="uz",
                client=fake_client,
            )

            result = provider.transcribe(f"file://{audio_path}", "uz-Latn")

        self.assertEqual(result.text, "Salom, meni eshityapsanmi?")
        self.assertEqual(result.language, "uz")
        self.assertEqual(result.confidence, 0.91)
        self.assertEqual(result.provider_id, "elevenlabs_stt")
        self.assertEqual(len(fake_client.calls), 1)
        self.assertEqual(fake_client.calls[0]["model_id"], "scribe_v2")
        self.assertEqual(fake_client.calls[0]["language_code"], "uz")
        self.assertNotIn("test-secret", repr(provider))

    def test_transcribe_rejects_missing_key_before_http_call(self):
        fake_client = FakeElevenLabsSTTClient()
        provider = ElevenLabsSTTProvider(
            api_key_configured=False,
            api_key_env="ELEVENLABS_API_KEY",
            api_key="",
            client=fake_client,
        )

        with self.assertRaisesRegex(ValueError, "ELEVENLABS_API_KEY"):
            provider.transcribe("file:///tmp/audio.webm", "uz-Latn")

        self.assertEqual(fake_client.calls, [])

    def test_missing_speech_to_text_permission_has_actionable_error(self):
        body = (
            b'{"detail":{"type":"authentication_error","code":"missing_permissions",'
            b'"message":"The API key you used is missing the permission '
            b'speech_to_text to execute this operation."}}'
        )
        error = HTTPError(
            url="https://api.elevenlabs.io/v1/speech-to-text",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(body),
        )

        message = _elevenlabs_stt_http_error_message(error)
        error.close()

        self.assertIn("speech_to_text permission", message)
        self.assertIn("restart the local stack", message)


if __name__ == "__main__":
    unittest.main()
