from __future__ import annotations

from companion_core.config import ProviderRuntimeConfig, load_runtime_config
from companion_core.providers import (
    LocalVoiceAnalysisProvider,
    LocalCompanionLLMProvider,
    MockLLMProvider,
    MockSTTProvider,
    MockTTSProvider,
    ProviderRegistry,
)
from companion_core.providers.openai_llm import OpenAILLMProvider
from companion_core.providers.openai_stt import OpenAISTTProvider
from companion_core.providers.stt import ElevenLabsSTTProvider
from companion_core.providers.tts import ElevenLabsTTSProvider, KokoroTTSProvider
from companion_core.providers.hume import HumeFixtureClient
from companion_core.providers.voice_analysis import (
    AssemblyAIVoiceAnalysisProvider,
    DeepgramVoiceAnalysisProvider,
    HumeVoiceAnalysisProvider,
)


def build_default_registry(config: ProviderRuntimeConfig | None = None) -> ProviderRegistry:
    config = config or load_runtime_config()
    registry = ProviderRegistry()
    registry.register_stt(MockSTTProvider())
    registry.register_stt(
        ElevenLabsSTTProvider(
            api_key_configured=config.elevenlabs_api_key_configured,
            api_key_env=config.elevenlabs_api_key_env,
            api_key=config.elevenlabs_api_key,
            model_id=config.elevenlabs_stt_model_id,
            base_url=config.elevenlabs_base_url,
            language_code=config.elevenlabs_stt_language_code,
        )
    )
    registry.register_stt(
        OpenAISTTProvider(
            api_key_configured=config.openai_api_key_configured,
            api_key_env=config.openai_api_key_env,
            api_key=config.openai_api_key,
            model=config.openai_stt_model,
            base_url=config.openai_base_url,
            language_code=config.openai_stt_language_code,
        )
    )
    registry.register_llm(MockLLMProvider())
    registry.register_llm(LocalCompanionLLMProvider())
    registry.register_llm(
        OpenAILLMProvider(
            api_key_configured=config.openai_api_key_configured,
            api_key_env=config.openai_api_key_env,
            api_key=config.openai_api_key,
            model=config.openai_model,
            base_url=config.openai_base_url,
        )
    )
    registry.register_tts(MockTTSProvider())
    registry.register_tts(
        ElevenLabsTTSProvider(
            api_key_configured=config.elevenlabs_api_key_configured,
            api_key_env=config.elevenlabs_api_key_env,
            api_key=config.elevenlabs_api_key,
            voice_id=config.elevenlabs_voice_id,
            model_id=config.elevenlabs_model_id,
            base_url=config.elevenlabs_base_url,
            output_format=config.elevenlabs_output_format,
            language_code=config.elevenlabs_language_code,
            audio_cache_dir=config.audio_cache_dir,
        )
    )
    registry.register_tts(
        KokoroTTSProvider(
            model_path=config.kokoro_model_path,
            voice_name=config.kokoro_voice_name,
        )
    )
    registry.register_voice_analysis(LocalVoiceAnalysisProvider())
    registry.register_voice_analysis(
        HumeVoiceAnalysisProvider(
            api_key_env=config.hume_api_key_env,
            api_key_configured=config.hume_api_key_configured,
            base_url=config.hume_base_url,
            client=HumeFixtureClient(config.hume_fixture_path)
            if config.hume_fixture_path
            else None,
        )
    )
    registry.register_voice_analysis(
        AssemblyAIVoiceAnalysisProvider(
            api_key_env=config.assemblyai_api_key_env,
            api_key_configured=config.assemblyai_api_key_configured,
        )
    )
    registry.register_voice_analysis(
        DeepgramVoiceAnalysisProvider(
            api_key_env=config.deepgram_api_key_env,
            api_key_configured=config.deepgram_api_key_configured,
        )
    )
    return registry
