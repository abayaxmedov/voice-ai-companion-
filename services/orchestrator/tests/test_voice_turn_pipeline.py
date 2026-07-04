import sys
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.app import build_dev_pipeline  # noqa: E402
from companion_core.config import ProviderRuntimeConfig  # noqa: E402
from companion_core.contracts import (  # noqa: E402
    ProviderHealth,
    ProviderKind,
    RuntimeState,
    TranscriptResult,
    VoiceAnalysisResult,
    VoiceTurnRequest,
)
from companion_core.providers.base import VoiceAnalysisProvider  # noqa: E402


class AnxiousVoiceAnalysisProvider(VoiceAnalysisProvider):
    provider_id = "test_anxious_analysis"

    def health(self):
        return ProviderHealth(self.provider_id, ProviderKind.VOICE_ANALYSIS, ready=True)

    def analyze(self, audio_ref: str | None, transcript: TranscriptResult):
        del audio_ref, transcript
        return VoiceAnalysisResult(
            provider_id=self.provider_id,
            status="ok",
            emotion="anxious",
            sentiment="negative",
        )


class VoiceTurnPipelineTests(unittest.TestCase):
    def test_transcript_override_generates_avatar_job(self):
        pipeline, agent = build_dev_pipeline(ProviderRuntimeConfig())
        result = pipeline.run(
            VoiceTurnRequest(
                session_id="test-session",
                agent_id=agent.agent_id,
                transcript_override="Bugun Toshkentda ob-havo qanday?",
            ),
            agent,
        )

        self.assertEqual(result.state, RuntimeState.SPEAKING)
        self.assertEqual(result.transcript.provider_id, "transcript_override")
        self.assertEqual(result.analysis.status, "ok")
        self.assertEqual(result.avatar_job.avatar_id, "metahuman_default")
        self.assertTrue(result.avatar_job.audio_ref.startswith("mock://"))
        self.assertGreaterEqual(len(result.avatar_job.visemes), 2)

    def test_voice_request_requires_audio_or_transcript(self):
        pipeline, agent = build_dev_pipeline(ProviderRuntimeConfig())

        with self.assertRaises(ValueError):
            pipeline.run(
                VoiceTurnRequest(session_id="test-session", agent_id=agent.agent_id),
                agent,
            )

    def test_spoken_response_is_plain_text(self):
        pipeline, agent = build_dev_pipeline(ProviderRuntimeConfig())
        result = pipeline.run(
            VoiceTurnRequest(
                session_id="test-session",
                agent_id=agent.agent_id,
                transcript_override="Menga qisqa javob ber.",
            ),
            agent,
        )

        self.assertNotIn("```", result.llm_response.response)
        self.assertNotIn("|", result.llm_response.response)
        self.assertNotIn("# ", result.llm_response.response)

    def test_voice_analysis_emotion_guides_avatar_mood(self):
        pipeline, agent = build_dev_pipeline(
            ProviderRuntimeConfig(voice_analysis_provider_id="local_voice_analysis")
        )
        pipeline._registry.register_voice_analysis(AnxiousVoiceAnalysisProvider())
        pipeline._selection = type(pipeline._selection)(
            stt_provider_id=pipeline._selection.stt_provider_id,
            llm_provider_id=pipeline._selection.llm_provider_id,
            tts_provider_id=pipeline._selection.tts_provider_id,
            voice_analysis_provider_id="test_anxious_analysis",
        )

        result = pipeline.run(
            VoiceTurnRequest(
                session_id="test-session",
                agent_id=agent.agent_id,
                transcript_override="Men biroz xavotirdaman.",
            ),
            agent,
        )

        self.assertEqual(result.avatar_job.mood, "reassuring")

    def test_hume_fixture_can_drive_full_voice_turn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path = Path(tmpdir) / "hume.json"
            fixture_path.write_text(
                json.dumps(
                    {
                        "predictions": [
                            {
                                "models": {
                                    "prosody": {
                                        "grouped_predictions": [
                                            {
                                                "predictions": [
                                                    {
                                                        "emotions": [
                                                            {"name": "Joy", "score": 0.18},
                                                            {"name": "Anxiety", "score": 0.91},
                                                        ],
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            pipeline, agent = build_dev_pipeline(
                ProviderRuntimeConfig(
                    voice_analysis_provider_id="hume",
                    hume_api_key_configured=True,
                    hume_fixture_path=str(fixture_path),
                )
            )
            result = pipeline.run(
                VoiceTurnRequest(
                    session_id="test-session",
                    agent_id=agent.agent_id,
                    audio_ref="file:///tmp/test.wav",
                    transcript_override="Men hozir xavotirdaman.",
                ),
                agent,
            )

        self.assertEqual(result.analysis.provider_id, "hume")
        self.assertEqual(result.analysis.emotion, "anxious")
        self.assertEqual(result.avatar_job.mood, "reassuring")


if __name__ == "__main__":
    unittest.main()
