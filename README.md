# Voice-Only AI Companion

Custom macOS voice-only AI avatar platform. The product goal is a local-first
desktop app where the user speaks in Uzbek and a MetaHuman-level avatar answers
by voice, with tool use, provider switching, and safe permissions.

This repository intentionally does **not** copy Unclaw/Grace names, assets,
code, prompts, or proprietary UI. The target is the same class of experience and
logic, implemented as a custom product.

## Non-negotiable Product Rules

- macOS first.
- Voice-only first screen: no chat-first UI.
- Uzbek voice input and Uzbek avatar speech are release blockers.
- MetaHuman is the avatar path.
- ElevenLabs and Kokoro must exist behind provider contracts; ElevenLabs can
  provide both STT and TTS for the first real speech-to-speech path.
- Voice analysis must be multi-provider, not hardcoded to one vendor.
- All provider keys are stored through secure local storage, never in logs.
- Risky tools require confirmation before action.

## Monorepo Map

```text
apps/desktop/                 macOS desktop shell and avatar viewport
services/orchestrator/         Python local AI orchestration server
services/avatar-bridge/        Unreal/MetaHuman playback bridge
packages/contracts/            Shared DTOs and event schemas
unreal/CompanionAvatar/        Unreal/MetaHuman project placeholder and docs
assets/avatars/                Avatar manifests and license notes
docs/                          Architecture, decisions, implementation notes
scripts/dev/                   Local development scripts
```

## Current State

This is the first implementation foundation. It contains:

- Python domain contracts for voice turns, providers, avatar jobs, tools, and
  voice analysis.
- Provider adapter skeletons for STT, LLM, TTS, and voice analysis.
- Live ElevenLabs STT/TTS adapters. With `COMPANION_VOICE_MODE=pipeline`,
  `COMPANION_STT_PROVIDER=elevenlabs_stt`, and
  `COMPANION_TTS_PROVIDER=elevenlabs`, mic audio is transcribed through
  ElevenLabs Scribe and answered through ElevenLabs voice synthesis.
- Safe audio playback endpoint for cached TTS files, so browser and avatar
  runtimes can play generated audio through HTTP.
- Hume EVI speech-to-speech websocket proxy for browser mic audio without
  exposing the Hume API key to frontend JavaScript.
- MetaHuman avatar bridge contract docs.
- Tests for the core orchestration contract.

## First Local Check

```bash
python3 -m unittest discover services/orchestrator/tests
```

## Run Local Orchestrator

This works without FastAPI and without external provider keys. It uses mock
providers so the contract can be tested immediately.

```bash
python3 scripts/dev/run_stack.py
python3 scripts/dev/smoke_runtime.py --mark-stream-ready
```

Frontend:

```text
http://127.0.0.1:5173
```

Individual services can still be run separately:

```bash
python3 scripts/dev/run_avatar_bridge.py --port 8770
python3 scripts/dev/run_orchestrator.py --port 8765
python3 scripts/dev/run_frontend.py --port 5173
```

Available endpoints:

- `GET /health`
- `GET /runtime/state`
- `GET /agents`
- `GET /providers/health`
- `GET /providers/catalog`
- `GET /audio/cache/<filename>`
- `GET /voice/hume-evi/ws` (WebSocket)
- `POST /audio/upload`
- `POST /voice/turn`

MetaHuman bridge endpoints:

- `GET http://127.0.0.1:8770/avatar/status`
- `GET http://127.0.0.1:8770/avatar/events`
- `POST http://127.0.0.1:8770/avatar/play`
- `POST http://127.0.0.1:8770/avatar/ready`

When Unreal Pixel Streaming is live, the bridge returns `player_url` and the
frontend embeds that URL in the MetaHuman viewport. During local mock testing,
`/avatar/ready` can mark the stream as ready without Unreal.

Example voice turn payload:

```json
{
  "session_id": "dev-session",
  "agent_id": "default",
  "transcript_override": "Salom, bugun Toshkentda ob-havo qanday?"
}
```

Example audio upload payload:

```json
{
  "session_id": "dev-session",
  "mime_type": "audio/webm",
  "audio_base64": "<base64 audio bytes>"
}
```

The upload returns a local `file://...` `audio_ref` that can be passed into
`POST /voice/turn`.

When a TTS provider creates local audio, the voice turn response exposes it as
`http://127.0.0.1:8765/audio/cache/<filename>` for frontend playback and avatar
bridge delivery.

## Handoff Rule

Any coder AI or developer continuing this project should start from
`docs/IMPLEMENTATION_BLUEPRINT.md` and preserve the public contracts before
adding features.

Provider key checklist: `docs/INTEGRATION_KEYS.md`.
