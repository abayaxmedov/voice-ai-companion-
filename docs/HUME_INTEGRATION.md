# Hume Integration Plan

Hume is the selected first provider for emotion/prosody analysis. The current
implementation does not send audio to Hume yet; it establishes the production
contract, local fixture path, and avatar mood mapping.

## Current Implementation

- Provider id: `hume`
- Config keys:
  - `HUME_API_KEY`
  - `HUME_BASE_URL`
  - `HUME_FIXTURE_PATH`
- Selected by:
  - `COMPANION_VOICE_ANALYSIS_PROVIDER=hume`
- Mapper:
  - `services/orchestrator/companion_core/providers/hume.py`

The mapper accepts nested Hume-style payloads containing emotion scores and
normalizes them into `VoiceAnalysisResult`. The voice turn pipeline then maps
emotion to avatar mood:

| User emotion | Avatar mood |
| --- | --- |
| anxiety, anger, distress, fear | reassuring |
| sadness, disappointment, tiredness | empathetic |
| joy, excitement, amusement | warm |
| confusion, doubt | clarifying |
| calmness, interest, concentration | attentive |

## Next Live Step

When the Hume key is available, replace the fixture client with a live client
that sends local audio from `audio_ref` and returns a Hume-style payload to the
same mapper. The live client must:

- never log `HUME_API_KEY`;
- reject non-local or missing `audio_ref` values;
- enforce size/time limits before upload;
- degrade to `VoiceAnalysisResult.unavailable(...)` on API/network failure;
- preserve `local_voice_analysis` as fallback.
