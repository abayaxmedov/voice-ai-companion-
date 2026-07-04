# Unreal Avatar Event Contract

All events are JSON.

## backend -> Unreal

```json
{
  "type": "avatar.play",
  "payload": {
    "job_id": "uuid",
    "turn_id": "uuid",
    "avatar_id": "metahuman_default",
    "audio_ref": "file:///local/turn.wav",
    "mood": "thoughtful",
    "behavior": "speak",
    "visemes": [
      {"time_ms": 0, "name": "A", "weight": 0.7}
    ]
  }
}
```

## Unreal -> backend

```json
{
  "type": "avatar.completed",
  "payload": {
    "job_id": "uuid",
    "turn_id": "uuid",
    "playback_ms": 2800,
    "dropped_frames": 0
  }
}
```

