import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion_core.contracts import TranscriptResult  # noqa: E402
from companion_core.providers.hume import (  # noqa: E402
    avatar_mood_from_emotion,
    hume_result_from_payload,
)


class HumeProviderTests(unittest.TestCase):
    def test_maps_nested_prosody_emotions(self):
        payload = {
            "predictions": [
                {
                    "models": {
                        "prosody": {
                            "grouped_predictions": [
                                {
                                    "predictions": [
                                        {
                                            "emotions": [
                                                {"name": "Calmness", "score": 0.21},
                                                {"name": "Anxiety", "score": 0.87},
                                                {"name": "Interest", "score": 0.52},
                                            ],
                                            "speaking_rate_wpm": 134,
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            ]
        }

        result = hume_result_from_payload(
            payload,
            TranscriptResult(text="Menga yordam kerak.", confidence=0.94),
        )

        self.assertEqual(result.provider_id, "hume")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.emotion, "anxious")
        self.assertEqual(result.sentiment, "negative")
        self.assertEqual(result.speaking_rate_wpm, 134)
        self.assertEqual(result.raw_summary["top_emotion"], "Anxiety")

    def test_avatar_mood_uses_user_emotion_as_hint(self):
        anxious = hume_result_from_payload(
            {"emotions": [{"name": "Anxiety", "score": 0.9}]},
            TranscriptResult(text="Nima qilishni bilmayapman."),
        )
        joyful = hume_result_from_payload(
            {"emotions": [{"name": "Joy", "score": 0.81}]},
            TranscriptResult(text="Zo'r bo'ldi."),
        )

        self.assertEqual(avatar_mood_from_emotion("thoughtful", anxious), "reassuring")
        self.assertEqual(avatar_mood_from_emotion("thoughtful", joyful), "warm")

    def test_missing_emotions_degrades_safely(self):
        result = hume_result_from_payload({}, TranscriptResult(text="Salom"))

        self.assertEqual(result.status, "unavailable")
        self.assertIn("prosody emotions", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
