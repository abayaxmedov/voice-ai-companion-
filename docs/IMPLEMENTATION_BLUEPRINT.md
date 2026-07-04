# Implementation Blueprint

This is the engineering handoff for building the project from the TZ.

## Product Target

Build a macOS local-first voice companion. User speaks in Uzbek. The system
transcribes speech, reasons through a multi-provider LLM layer, optionally uses
permissioned tools, synthesizes Uzbek speech, analyzes the voice/response, and
drives a MetaHuman avatar that speaks back.

## Core Runtime Flow

```text
Desktop microphone
  -> audio session
  -> VAD/STT
  -> voice analysis
  -> intent/tool router
  -> LLM response contract
  -> TTS provider
  -> lip-sync/emotion plan
  -> MetaHuman avatar playback job
  -> WebRTC/Pixel Streaming viewport
```

## Required Contracts

- `VoiceTurnRequest`: one user utterance or transcript override.
- `VoiceTurnResult`: transcript, spoken response, analysis, audio, avatar job.
- `ProviderHealth`: standard provider readiness object.
- `VoiceAnalysisResult`: emotion, sentiment, speaker, audio quality, language.
- `AvatarPlaybackJob`: the only object the avatar bridge should need to play a
  turn.

## Current Local API

The current local orchestrator is intentionally zero-dependency so the contract
can run before FastAPI is installed.

```text
GET  /health
GET  /runtime/state
GET  /agents
GET  /providers/health
POST /voice/turn
```

`POST /voice/turn` accepts `session_id`, `agent_id`, `audio_ref` or
`transcript_override`, `interrupt_previous`, and `user_locale`.

## MetaHuman Integration Requirements

- Unreal runtime must accept JSON events from `services/avatar-bridge`.
- The bridge must support: `avatar.ready`, `avatar.state`, `avatar.play`,
  `avatar.interrupt`, `avatar.completed`, `avatar.error`, `avatar.switch`.
- Lip sync can begin with approximate visemes, but final MVP must make mouth
  movement visibly aligned with Uzbek speech.
- If Pixel Streaming is unavailable on a target Mac, that is a release blocker
  unless the product owner approves an alternate local render path.

## Voice Analysis Requirements

Voice analysis must not block the entire conversation if a vendor is down. The
pipeline should have a timeout and fallback order:

1. Local lightweight audio quality/prosody analysis.
2. Cloud provider analysis when enabled and keys are configured.
3. Degraded mode with `analysis_status=unavailable`.

Canonical analysis fields:

- detected language and confidence
- user emotion/prosody labels
- sentiment
- speaking rate
- interruption/barge-in flag
- audio quality warnings
- optional diarization/speaker labels

## Safety Rules

- Browser submit, computer control, file delete, message send, payment, and
  account actions require explicit confirmation.
- Raw private audio and API keys are never written to normal logs.
- Provider adapters return redacted errors.
