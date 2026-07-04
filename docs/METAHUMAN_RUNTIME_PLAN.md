# MetaHuman Runtime Plan

## Goal

Use MetaHuman as the production avatar path. The final MVP must not ship with a
flat placeholder avatar.

## Milestone 1: Minimal Runtime

- Create Unreal project under `unreal/CompanionAvatar`.
- Add one licensed/custom MetaHuman.
- Create a neutral companion scene:
  - camera framed for desktop companion view
  - soft lighting
  - idle animation
  - listening/thinking/speaking state hooks
- Enable Pixel Streaming / Pixel Streaming 2 for local app embedding.
- Expose a local event receiver for JSON avatar events.

## Current Bridge

The repository now includes a local MetaHuman bridge service:

```bash
python scripts/dev/run_avatar_bridge.py --port 8770
```

Bridge API:

```text
GET  /avatar/status
GET  /avatar/events
POST /avatar/ready
POST /avatar/state
POST /avatar/play
POST /avatar/interrupt
```

The orchestrator sends every `AvatarPlaybackJob` to `POST /avatar/play`.
Until Unreal is connected, events are queued and visible through
`GET /avatar/events`.

## Milestone 2: Speech Playback

- Accept `avatar.play` events from `services/avatar-bridge`.
- Load audio from a local file or internal URL.
- Play audio through the avatar runtime.
- Drive jaw/lip movement with initial viseme frames.
- Emit `avatar.completed` when playback ends.
- Support `avatar.interrupt` within 200 ms target.

## Milestone 3: Quality

- Replace approximate mouth motion with production lip-sync.
- Add emotion mapping:
  - neutral
  - thoughtful
  - happy
  - concerned
  - apologetic
  - excited
- Add natural gaze, blink, and head motion.
- Measure A/V sync.

## Release Blockers

- Blank avatar viewport.
- Frozen face during speech.
- No interrupt support.
- Unlicensed avatar asset.
- Pixel Streaming not working on the target Mac without approved fallback.
