# CompanionAvatar Unreal Project

This folder is reserved for the Unreal Engine MetaHuman runtime.

## Required Runtime Features

- MetaHuman or MetaHuman-level character.
- Pixel Streaming / WebRTC local stream into the desktop app.
- JSON event receiver for avatar state and playback jobs.
- Lip-sync receiver that accepts viseme frames.
- Emotion/state animation mapping:
  - idle
  - listening
  - thinking
  - speaking
  - acting
  - interrupted
  - error

## No Proprietary Copy Rule

Do not import Unclaw/Grace assets, brand, bundled models, or proprietary
materials. Use licensed MetaHuman assets and custom project art.

## First Unreal Milestone

1. Create a minimal MetaHuman scene.
2. Enable Pixel Streaming 2 for local testing.
3. Implement event receiver stubs:
   - `avatar.state`
   - `avatar.play`
   - `avatar.interrupt`
4. Stream first frame into desktop viewport.
5. Play a local WAV and drive basic jaw animation.

