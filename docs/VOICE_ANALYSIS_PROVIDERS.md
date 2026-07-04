# Voice Analysis Provider Strategy

## Goal

Voice analysis improves how the avatar reacts to user speech. It should help
detect emotion, sentiment, audio quality, speaking rate, and interruption
signals. It must be optional and provider-agnostic.

## Canonical Result

All providers must map into `VoiceAnalysisResult`:

- provider_id
- status
- language
- language_confidence
- sentiment
- emotion
- speaking_rate_wpm
- audio_quality
- warnings
- raw_summary

## Provider Families

| Provider family | Role | MVP behavior |
|---|---|---|
| Local basic analysis | Always-on fallback | Simple transcript/audio metadata, never blocks turns |
| Hume-style expression analysis | Emotion/prosody | Cloud optional, key required |
| AssemblyAI-style speech intelligence | Sentiment/chapters/diarization style output | Cloud optional, key required |
| Deepgram-style STT analytics | Realtime STT and speech analytics | Cloud optional, key required |
| Future provider | Replaceable adapter | Must implement `VoiceAnalysisProvider` |

## Professional Rules

- Analysis failure must not kill a conversation.
- Any cloud analysis must be explicitly enabled by the user.
- Raw private audio should not be retained unless debug mode is enabled.
- Uzbek capability must be tested, not assumed.
- The avatar can use analysis only as a hint, never as the sole source of truth.

## First Implementation Target

1. Keep `LocalVoiceAnalysisProvider` as default.
2. Add config model for enabled voice analysis providers.
3. Implement one real cloud provider behind the interface.
4. Add timeout and fallback.
5. Add diagnostics panel showing provider status and last analysis result.

