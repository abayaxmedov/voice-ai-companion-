import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.app import build_dev_pipeline  # noqa: E402
from companion_core.config import ProviderRuntimeConfig  # noqa: E402
from companion_core.contracts import VoiceTurnRequest  # noqa: E402
from companion_core.pipeline.audio_mouth import StreamingMouthAnalyzer  # noqa: E402
from companion_core.pipeline.voice_turn import StreamingUnsupported  # noqa: E402
from companion_core.providers.tts import voice_settings_for  # noqa: E402


def _sine_pcm(freq: float, seconds: float, rate: int) -> bytes:
    n = int(seconds * rate)
    return struct.pack(
        "<%dh" % n,
        *[int(20000 * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)],
    )


class FakeStreamingTTS:
    provider_id = "fake_stream_tts"
    output_format = "pcm_16000"

    def __init__(self, cache_dir: str) -> None:
        self.audio_cache_dir = cache_dir

    def synthesize(self, text, voice_profile_id, language):  # pragma: no cover
        raise AssertionError("streaming path must be used")

    def synthesize_stream(self, text, voice_profile_id, language, mood, speech_style):
        del text, voice_profile_id, language, mood, speech_style
        rate = 16000
        yield _sine_pcm(220, 0.2, rate), {
            "characters": ["s", "a"],
            "character_start_times_seconds": [0.0, 0.1],
            "character_end_times_seconds": [0.1, 0.2],
        }
        yield _sine_pcm(240, 0.2, rate), {
            "characters": ["l", "o", "m"],
            "character_start_times_seconds": [0.2, 0.26, 0.34],
            "character_end_times_seconds": [0.26, 0.34, 0.4],
        }


class StreamingTurnTests(unittest.TestCase):
    def _request(self, agent):
        return VoiceTurnRequest(
            session_id="s",
            agent_id=agent.agent_id,
            transcript_override="Salom dunyo.",
        )

    def test_mock_tts_raises_streaming_unsupported_before_any_emit(self):
        pipeline, agent = build_dev_pipeline(ProviderRuntimeConfig())
        events = []
        with self.assertRaises(StreamingUnsupported):
            pipeline.run_streaming(self._request(agent), agent, [], events.append)
        self.assertEqual(events, [])

    def test_streaming_emits_meta_audio_and_returns_result(self):
        pipeline, agent = build_dev_pipeline(ProviderRuntimeConfig())
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeStreamingTTS(tmp)
            tts_id = pipeline._selection.tts_provider_id  # noqa: SLF001 - test wiring
            pipeline._registry.tts[tts_id] = fake  # noqa: SLF001 - test wiring

            events = []
            result = pipeline.run_streaming(self._request(agent), agent, [], events.append)

            types = [e["type"] for e in events]
            self.assertEqual(types[0], "meta")
            self.assertGreaterEqual(types.count("audio"), 2)
            audio_events = [e for e in events if e["type"] == "audio"]
            self.assertTrue(any(e["curves"] for e in audio_events))
            self.assertTrue(any(e["visemes"] for e in audio_events))
            self.assertTrue(result.tts.audio_ref.endswith(".wav"))
            self.assertTrue(Path(result.tts.audio_ref.removeprefix("file://")).is_file())
            self.assertGreaterEqual(len(result.avatar_job.visemes), 2)
            self.assertIn("tts_first_chunk_ms", result.latency_ms)


class VoiceSettingsTests(unittest.TestCase):
    def test_excited_is_less_stable_than_reassuring(self):
        excited = voice_settings_for("excited", "normal")
        calm = voice_settings_for("reassuring", "normal")
        self.assertLess(excited["stability"], calm["stability"])
        self.assertGreater(excited["style"], calm["style"])

    def test_speech_style_shifts_and_clamps(self):
        whisper = voice_settings_for("excited", "whisper")
        self.assertGreater(whisper["stability"], voice_settings_for("excited", "normal")["stability"])
        self.assertLessEqual(whisper["style"], 1.0)
        self.assertGreaterEqual(whisper["stability"], 0.0)


class StreamingAnalyzerTests(unittest.TestCase):
    def test_incremental_frames_cover_fed_audio(self):
        rate = 16000
        analyzer = StreamingMouthAnalyzer(rate)
        total_frames = 0
        for _ in range(4):
            out = analyzer.feed(_sine_pcm(220, 0.1, rate))
            if out:
                self.assertEqual(out["fps"], 50)
                total_frames += len(out["jaw"])
                for key in ("energy", "close", "spread", "round", "pitch"):
                    self.assertEqual(len(out[key]), len(out["jaw"]))
        # 0.4s audio ≈ 20 kadr (50fps)
        self.assertGreaterEqual(total_frames, 18)
        self.assertLessEqual(total_frames, 21)


if __name__ == "__main__":
    unittest.main()
