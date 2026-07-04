# Next Sprint

## Sprint Goal

Turn the scaffold into a runnable local prototype:

User transcript override or microphone input -> local orchestrator -> mock/real
LLM -> mock/real TTS -> avatar bridge event -> desktop-visible status.

## Ordered Tasks

1. Keep zero-dependency local HTTP API stable while FastAPI dependency is added.
2. Add SQLite config and agent profile storage.
3. Build Electron/Tauri shell that can start the backend.
4. Add push-to-talk capture or transcript override dev panel.
5. Replace Hume fixture client with live Hume audio analysis once key/account is ready.
6. Done: implement ElevenLabs HTTP synthesis behind the configured provider boundary.
7. Done: serve cached TTS audio through a safe local HTTP endpoint.
8. Add Kokoro local runtime adapter after model and voice files are selected.
9. Create Unreal MetaHuman project and local Pixel Streaming proof.
10. Connect Unreal project to the existing MetaHuman bridge event queue.
11. Expand Uzbek regression tests.

## Definition of Done

- `python -m unittest discover services/orchestrator/tests` passes.
- Dev voice turn creates a valid avatar playback job.
- `GET /health` and `POST /voice/turn` work on the local orchestrator.
- Desktop can show backend health.
- MetaHuman runtime plan has an owner and target UE version.
- Voice analysis provider selection is configurable.
- `GET /providers/catalog` exposes selected and optional provider readiness.
- `POST /audio/upload` can save local mic recordings and return `audio_ref`.
- Hume-style emotion payloads can drive avatar mood in the voice turn pipeline.
- Cached TTS files can be played by the frontend through `/audio/cache/<filename>`.
- Local `.env` values are auto-loaded in dev without exposing secrets in health/catalog output.
- Hume EVI speech-to-speech mode can stream browser mic chunks through a local
  websocket proxy without exposing the Hume API key to frontend JavaScript.
