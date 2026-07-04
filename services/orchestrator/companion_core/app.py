from __future__ import annotations

from companion_core.config import ProviderRuntimeConfig, load_runtime_config
from companion_core.contracts import AgentProfile, VoiceTurnRequest
from companion_core.pipeline.voice_turn import PipelineProviderSelection, VoiceTurnPipeline
from companion_core.providers.factory import build_default_registry


def build_dev_pipeline(config: ProviderRuntimeConfig | None = None) -> tuple[VoiceTurnPipeline, AgentProfile]:
    config = config or load_runtime_config()
    registry = build_default_registry(config)
    selection = PipelineProviderSelection(
        stt_provider_id=config.stt_provider_id,
        llm_provider_id=config.llm_provider_id,
        tts_provider_id=config.tts_provider_id,
        voice_analysis_provider_id=config.voice_analysis_provider_id,
    )
    pipeline = VoiceTurnPipeline(registry, selection)
    agent = AgentProfile(
        agent_id="default",
        display_name="Custom Companion",
        avatar_id="metahuman_default",
        voice_profile_id="uzbek_default",
        enabled_tools=("web_search", "weather", "reminders"),
    )
    return pipeline, agent


def run_dev_turn(transcript: str) -> dict[str, object]:
    pipeline, agent = build_dev_pipeline()
    result = pipeline.run(
        VoiceTurnRequest(
            session_id="dev-session",
            agent_id=agent.agent_id,
            transcript_override=transcript,
        ),
        agent,
    )
    return {
        "turn_id": result.turn_id,
        "transcript": result.transcript.text,
        "response": result.llm_response.response,
        "analysis": result.analysis.status,
        "avatar_job": result.avatar_job.job_id,
        "audio_ref": result.tts.audio_ref,
    }
