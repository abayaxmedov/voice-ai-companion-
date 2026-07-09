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

## Electron -> backend -> Unreal (audio pozitsiya sinxroni)

Electron audio ijrosi davomida har ~500ms `POST /avatar/sync` yuboradi;
bridge uni navbatga `avatar.sync` sifatida qo'yadi. UE poller hodisaning
`created_at`idan latency'ni hisoblab qo'shadi (bir mashina — soatlar bir xil)
va `LipSync.SyncPlaybackTime(position)` chaqiradi.

```json
{
  "type": "avatar.sync",
  "payload": {
    "avatar_id": "metahuman_default",
    "turn_id": null,
    "position_ms": 1500.0
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

