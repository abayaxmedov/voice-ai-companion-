# Avatar Bridge

This service owns the boundary between the local orchestrator and Unreal /
MetaHuman runtime.

It must stay small and deterministic:

- receive `AvatarPlaybackJob`
- translate it into Unreal JSON events
- monitor Unreal/Pixel Streaming health
- support interrupt and avatar switching
- report playback completion/errors

The bridge must not call LLM/TTS/STT providers directly.

