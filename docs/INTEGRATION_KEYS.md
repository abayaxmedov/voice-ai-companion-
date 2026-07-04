# Integration Keys Checklist

This project must run locally with mock providers, then upgrade provider by
provider. Never paste keys into chat, code, screenshots, or logs. Put them in a
local `.env` file at the project root or a macOS Keychain-backed loader when
that storage layer is added. Dev scripts auto-load `.env`; real shell
environment variables still override `.env` values.

## Required Later

### ElevenLabs

- Needed for: cloud STT and TTS path.
- Get from: ElevenLabs dashboard API keys.
- Set locally:
  - `ELEVENLABS_API_KEY`
  - `ELEVENLABS_VOICE_ID`
  - optional `ELEVENLABS_STT_MODEL_ID` (default `scribe_v2`)
  - optional `ELEVENLABS_STT_LANGUAGE_CODE` (default `uz`)
  - `ELEVENLABS_MODEL_ID`
  - optional `ELEVENLABS_OUTPUT_FORMAT` (default `mp3_44100_128`)
  - optional `ELEVENLABS_LANGUAGE_CODE` (use `auto` to omit the TTS language code)
- Required permissions: the key must include ElevenLabs `speech_to_text` and
  `text_to_speech` permissions. A conversation token, single-use token, or
  service-account key without these scopes will fail with `unauthorized` or
  `missing_permissions`.
- Selection:
  - `COMPANION_STT_PROVIDER=elevenlabs_stt`
  - `COMPANION_LLM_PROVIDER=local_companion` until a real LLM is connected
  - `COMPANION_TTS_PROVIDER=elevenlabs`
- Runtime behavior: the orchestrator sends uploaded mic audio to ElevenLabs
  Scribe, generates an Uzbek response, sends that text to ElevenLabs TTS,
  stores the returned audio under `COMPANION_AUDIO_CACHE_DIR`, and returns a
  local `/audio/cache/...` HTTP audio reference to the frontend and avatar
  bridge.
- Uzbek gate: do not accept the provider as production-ready until Uzbek sample
  speech passes pronunciation and latency checks.

If the frontend shows `ElevenLabs API key does not have text_to_speech
permission`, create or update the ElevenLabs key with `permissions:
["text_to_speech"]`, put the new value in `.env`, and restart the local stack.

Example local speech-to-speech switch:

```bash
COMPANION_VOICE_MODE=pipeline
COMPANION_STT_PROVIDER=elevenlabs_stt
COMPANION_LLM_PROVIDER=local_companion
COMPANION_TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=<set in local env only>
ELEVENLABS_VOICE_ID=<your selected Uzbek-capable voice id>
ELEVENLABS_STT_MODEL_ID=scribe_v2
ELEVENLABS_STT_LANGUAGE_CODE=uz
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
ELEVENLABS_LANGUAGE_CODE=auto
COMPANION_ORCHESTRATOR_PUBLIC_BASE_URL=http://127.0.0.1:8765
```

### Kokoro

- Needed for: local/offline TTS path.
- Get/download: local Kokoro model and voice files.
- Set locally:
  - `KOKORO_MODEL_PATH`
  - `KOKORO_VOICE_NAME`
- Selection:
  - `COMPANION_TTS_PROVIDER=kokoro`
- Uzbek gate: Kokoro must be tested with Uzbek Latin text before it can be a
  release voice.

### Voice Analysis Provider

Choose at least one cloud provider for the first real emotion/prosody pass.

- Hume:
  - `HUME_API_KEY`
  - `HUME_EVI_CONFIG_ID` for speech-to-speech mode
  - optional `COMPANION_VOICE_MODE=hume_evi`
  - optional dev-only `HUME_FIXTURE_PATH` for testing saved JSON responses
  - `COMPANION_VOICE_ANALYSIS_PROVIDER=hume`
- AssemblyAI:
  - `ASSEMBLYAI_API_KEY`
  - `COMPANION_VOICE_ANALYSIS_PROVIDER=assemblyai`
- Deepgram:
  - `DEEPGRAM_API_KEY`
  - `COMPANION_VOICE_ANALYSIS_PROVIDER=deepgram`

## Hume Development Flow

Until live Hume calls are enabled, the project supports a local fixture path:

```bash
COMPANION_VOICE_ANALYSIS_PROVIDER=hume
HUME_API_KEY=local-placeholder-or-real-key
HUME_FIXTURE_PATH=/absolute/path/to/hume-response.json
```

The fixture must contain Hume-style `emotions` objects, even if they are nested
inside model/prediction structures. The adapter maps the strongest emotion to
`VoiceAnalysisResult.emotion`; the pipeline then converts that signal into an
avatar mood such as `reassuring`, `empathetic`, `warm`, `clarifying`, or
`attentive`.

## Hume EVI Speech-to-Speech Flow

When `HUME_API_KEY` and `HUME_EVI_CONFIG_ID` are set, the dev UI can use Hume
EVI for speech-to-speech:

```bash
COMPANION_VOICE_MODE=hume_evi
HUME_API_KEY=<set in local env only>
HUME_EVI_CONFIG_ID=<your EVI configuration id>
HUME_EVI_WS_URL=wss://api.hume.ai/v0/evi/chat
```

The browser opens a local websocket at `/voice/hume-evi/ws`. The local
orchestrator proxies audio chunks to Hume's EVI websocket using the server-side
API key, so the API key is not exposed to browser JavaScript. Hume returns
`user_message`, `assistant_message`, `audio_output`, and `assistant_end` events;
the frontend queues `audio_output` WAV segments for playback.

`COMPANION_VOICE_MODE` defaults to `pipeline`. Select `hume_evi` explicitly only
when the Hume EVI configuration is ready. Uzbek is still a quality gate because
Hume EVI's documented language list does not include Uzbek.

## Useful Now

Keep these defaults while Unreal/Xcode is pending:

```bash
COMPANION_STT_PROVIDER=mock_stt
COMPANION_LLM_PROVIDER=mock_llm
COMPANION_TTS_PROVIDER=mock_tts
COMPANION_VOICE_ANALYSIS_PROVIDER=local_voice_analysis
```

Then check:

```bash
python3 scripts/dev/run_stack.py
curl http://127.0.0.1:8765/providers/catalog
```

The catalog shows every provider, whether its required key/model is configured,
and which provider is currently selected.
