import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.providers.tts import (  # noqa: E402
    ElevenLabsTTSProvider,
    _elevenlabs_http_error_message,
)


class FakeElevenLabsClient:
    def __init__(self, audio: bytes = b"fake-mp3-bytes"):
        self.audio = audio
        self.calls = []

    def create_speech(
        self,
        *,
        api_key: str,
        voice_id: str,
        model_id: str,
        text: str,
        output_format: str,
        language_code: str | None,
    ) -> bytes:
        self.calls.append(
            {
                "api_key": api_key,
                "voice_id": voice_id,
                "model_id": model_id,
                "text": text,
                "output_format": output_format,
                "language_code": language_code,
            }
        )
        return self.audio


class ElevenLabsTTSTests(unittest.TestCase):
    def test_synthesize_writes_audio_to_cache(self):
        fake_client = FakeElevenLabsClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = ElevenLabsTTSProvider(
                api_key_configured=True,
                api_key_env="ELEVENLABS_API_KEY",
                api_key="test-secret",
                voice_id="voice-123",
                model_id="eleven_flash_v2_5",
                output_format="mp3_44100_128",
                language_code="uz",
                audio_cache_dir=temp_dir,
                client=fake_client,
            )

            result = provider.synthesize(
                "  Salom, men Uzbek tilida gapiryapman.  ",
                voice_profile_id="app-voice-profile",
                language="uz-Latn",
            )

            self.assertEqual(result.provider_id, "elevenlabs")
            self.assertTrue(result.audio_ref.startswith("file://"))
            self.assertEqual(result.sample_rate_hz, 44100)
            self.assertEqual(result.timing["language_code"], "uz")

            audio_path = Path(result.audio_ref.removeprefix("file://"))
            self.assertEqual(audio_path.parent, Path(temp_dir))
            self.assertEqual(audio_path.suffix, ".mp3")
            self.assertEqual(audio_path.read_bytes(), b"fake-mp3-bytes")

        self.assertEqual(len(fake_client.calls), 1)
        self.assertEqual(fake_client.calls[0]["voice_id"], "voice-123")
        self.assertEqual(fake_client.calls[0]["model_id"], "eleven_flash_v2_5")
        self.assertEqual(fake_client.calls[0]["text"], "Salom, men Uzbek tilida gapiryapman.")
        self.assertEqual(fake_client.calls[0]["output_format"], "mp3_44100_128")
        self.assertEqual(fake_client.calls[0]["language_code"], "uz")
        self.assertNotIn("test-secret", repr(provider))

    def test_synthesize_rejects_missing_key_before_http_call(self):
        fake_client = FakeElevenLabsClient()
        provider = ElevenLabsTTSProvider(
            api_key_configured=False,
            api_key_env="ELEVENLABS_API_KEY",
            api_key="",
            voice_id="voice-123",
            client=fake_client,
        )

        with self.assertRaisesRegex(ValueError, "ELEVENLABS_API_KEY"):
            provider.synthesize(
                "Salom",
                voice_profile_id="app-voice-profile",
                language="uz-Latn",
            )

        self.assertEqual(fake_client.calls, [])

    def test_auto_language_code_omits_language_code_from_payload(self):
        fake_client = FakeElevenLabsClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            provider = ElevenLabsTTSProvider(
                api_key_configured=True,
                api_key_env="ELEVENLABS_API_KEY",
                api_key="test-secret",
                voice_id="voice-123",
                language_code="auto",
                audio_cache_dir=temp_dir,
                client=fake_client,
            )

            result = provider.synthesize(
                "Salom",
                voice_profile_id="app-voice-profile",
                language="uz-Latn",
            )

        self.assertIsNone(result.timing["language_code"])
        self.assertIsNone(fake_client.calls[0]["language_code"])

    def test_missing_text_to_speech_permission_has_actionable_error(self):
        body = (
            b'{"detail":{"type":"authentication_error","code":"missing_permissions",'
            b'"message":"The API key you used is missing the permission '
            b'text_to_speech to execute this operation."}}'
        )
        error = HTTPError(
            url="https://api.elevenlabs.io/v1/text-to-speech/voice-123",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(body),
        )

        message = _elevenlabs_http_error_message(error)
        error.close()

        self.assertIn("text_to_speech permission", message)
        self.assertIn("restart the local stack", message)
        self.assertNotIn("request_id", message)


if __name__ == "__main__":
    unittest.main()
