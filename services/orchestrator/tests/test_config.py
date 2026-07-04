import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.config import load_runtime_config  # noqa: E402


class RuntimeConfigTests(unittest.TestCase):
    def test_load_runtime_config_reads_local_env_file_without_exposing_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "COMPANION_TTS_PROVIDER=elevenlabs",
                        "ELEVENLABS_API_KEY='local-secret'",
                        "ELEVENLABS_VOICE_ID=voice-123",
                        "COMPANION_ORCHESTRATOR_PUBLIC_BASE_URL=http://test.local",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"COMPANION_ENV_FILE": str(env_path)}, clear=True):
                config = load_runtime_config()

        self.assertEqual(config.tts_provider_id, "elevenlabs")
        self.assertEqual(config.stt_provider_id, "elevenlabs_stt")
        self.assertTrue(config.elevenlabs_api_key_configured)
        self.assertEqual(config.elevenlabs_api_key, "local-secret")
        self.assertEqual(config.elevenlabs_voice_id, "voice-123")
        self.assertEqual(config.orchestrator_public_base_url, "http://test.local")
        self.assertNotIn("local-secret", repr(config))

    def test_hume_evi_keys_do_not_override_pipeline_mode_by_default(self):
        config = load_runtime_config(
            {
                "HUME_API_KEY": "hume-secret",
                "HUME_EVI_CONFIG_ID": "config-123",
            }
        )

        self.assertEqual(config.voice_mode, "pipeline")
        self.assertEqual(config.hume_api_key, "hume-secret")
        self.assertEqual(config.hume_evi_config_id, "config-123")
        self.assertNotIn("hume-secret", repr(config))

    def test_hume_evi_mode_can_be_selected_explicitly(self):
        config = load_runtime_config(
            {
                "HUME_API_KEY": "hume-secret",
                "HUME_EVI_CONFIG_ID": "config-123",
                "COMPANION_VOICE_MODE": "hume_evi",
            }
        )

        self.assertEqual(config.voice_mode, "hume_evi")


if __name__ == "__main__":
    unittest.main()
