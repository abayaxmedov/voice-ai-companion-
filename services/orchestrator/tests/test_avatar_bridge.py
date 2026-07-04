import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "avatar-bridge"
sys.path.insert(0, str(ROOT))

from avatar_bridge.events import AvatarEvent, AvatarEventType  # noqa: E402
from avatar_bridge.runtime import MetaHumanBridgeRuntime  # noqa: E402
from avatar_bridge.serializer import serialize_event  # noqa: E402


class AvatarBridgeTests(unittest.TestCase):
    def test_serializes_unreal_event(self):
        event = AvatarEvent(
            event_type=AvatarEventType.PLAY,
            payload={"turn_id": "turn-1", "avatar_id": "metahuman_default"},
        )
        encoded = serialize_event(event)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["type"], "avatar.play")
        self.assertEqual(decoded["payload"]["avatar_id"], "metahuman_default")

    def test_runtime_queues_metahuman_play_event(self):
        runtime = MetaHumanBridgeRuntime()
        record = runtime.play(
            {
                "turn_id": "turn-1",
                "avatar_id": "metahuman_default",
                "audio_ref": "mock://audio.wav",
                "mood": "thoughtful",
                "behavior": "speak",
            }
        )

        status = runtime.status()
        events = runtime.next_events()

        self.assertEqual(record["type"], "avatar.play")
        self.assertEqual(status.last_event_type, "avatar.play")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["avatar_id"], "metahuman_default")


if __name__ == "__main__":
    unittest.main()
