# Architecture Decisions

## AD-001: Custom Product, No Proprietary Copy

We can match the class of behavior and user experience, but we must not copy
Unclaw/Grace names, assets, code, proprietary prompts, bundled models, or UI.
Brand, avatar assets, prompts, and visual design are custom.

## AD-002: MetaHuman Avatar Path

The avatar runtime will use MetaHuman or MetaHuman-level assets. Placeholder
2D avatars may be used only for early plumbing tests and cannot be accepted as
the final MVP avatar.

## AD-003: Voice-Only Main Interaction

The main app experience is voice and avatar. Text transcript can exist for
diagnostics or accessibility, but the product must work without a chat input.

## AD-004: Multi-Provider Adapters

LLM, STT, TTS, and voice analysis must use provider interfaces. Product logic
must not depend on a specific vendor response shape.

## AD-005: Voice Analysis Integrations

Voice analysis is a separate provider family. It can include local prosody
analysis, Hume-style expression analysis, AssemblyAI-style speech intelligence,
Deepgram-style STT analytics, or future vendors. The canonical result remains
our own `VoiceAnalysisResult`.

## AD-006: Uzbek Quality Gate

Uzbek language support is not assumed from any vendor. STT, LLM output, TTS, and
voice analysis must pass project-specific Uzbek tests before release.


## AD-007: MetaHuman Face Animation via LiveLink (2026-07-08)

The assembled UE 5.8 MetaHuman has no editable main Face AnimBP (the facial rig
lives in a fixed post-process ABP). Manual "Modify Curve" wiring is therefore
not viable. The face is driven through the shipped ARKit path instead:
`UCompanionLipSync` pushes ARKit curves as an in-process LiveLink subject
(`LLink_Face_Subj`), and `ACompanionDirector` enables `UseARKit` and swaps the
Face mesh to the stock `ABP_MH_LiveLink`. No Blueprint/AnimGraph editing is
required or allowed for lip-sync; runtime validation logs
"Yuz curve oqimi OK" after the first playback.
