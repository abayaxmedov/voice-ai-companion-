# Unreal / MetaHuman Setup

## Install Requirement

Unreal Engine is required to run the real 3D stream. Install it through Epic
Games Launcher, then open:

```text
unreal/CompanionAvatar/CompanionAvatar.uproject
```

The local Python stack can be started before Unreal:

```bash
python3 scripts/dev/run_stack.py
```

## Required Manual Steps in Unreal

1. Add/import a licensed MetaHuman.
2. Create `/Game/Maps/CompanionStage`.
3. Add the MetaHuman to the scene.
4. Add `CompanionBridgePoller` component to a scene actor.
5. In Blueprint, implement:
   - `OnAvatarReadyEvent`
   - `OnAvatarPlayEvent`
   - `OnAvatarStateEvent`
   - `OnAvatarInterruptEvent`
   - `OnAvatarCompletedEvent`
   - `OnAvatarErrorEvent`
6. Enable Pixel Streaming / Pixel Streaming 2.
7. Run local Pixel Streaming signaling so the player is reachable at:

```text
http://127.0.0.1:8888
```

## Current Event Flow

```text
Frontend -> Orchestrator /voice/turn
Orchestrator -> MetaHuman Bridge /avatar/play
Unreal CompanionBridgePoller -> /avatar/events?mode=poll
Blueprint -> MetaHuman audio/lip-sync/emotion
Unreal -> MetaHuman Bridge /avatar/ready with player_url
Frontend -> embeds player_url in iframe
```

## Release Blockers

- Unreal Engine not installed.
- MetaHuman not imported.
- Pixel Streaming player not reachable.
- Blueprint event handlers not wired.
- AudioRef still `mock://...` instead of real playable file/URL.
