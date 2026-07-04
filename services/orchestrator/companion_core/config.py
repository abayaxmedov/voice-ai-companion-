from __future__ import annotations

from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    stt_provider_id: str = "mock_stt"
    llm_provider_id: str = "mock_llm"
    tts_provider_id: str = "mock_tts"
    voice_analysis_provider_id: str = "local_voice_analysis"

    elevenlabs_api_key_env: str = "ELEVENLABS_API_KEY"
    elevenlabs_api_key: str = field(default="", repr=False, compare=False)
    elevenlabs_api_key_configured: bool = False
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_output_format: str = "pcm_24000"
    elevenlabs_language_code: str = "uz"
    elevenlabs_stt_model_id: str = "scribe_v2"
    elevenlabs_stt_language_code: str = "uz"

    kokoro_model_path: str = ""
    kokoro_voice_name: str = ""

    openai_api_key_env: str = "OPENAI_API_KEY"
    openai_api_key: str = field(default="", repr=False, compare=False)
    openai_api_key_configured: bool = False
    openai_base_url: str = "https://api.openai.com"
    openai_model: str = "gpt-4o-mini"
    openai_stt_model: str = "whisper-1"
    openai_stt_language_code: str = "uz"

    hume_api_key_env: str = "HUME_API_KEY"
    hume_api_key: str = field(default="", repr=False, compare=False)
    hume_api_key_configured: bool = False
    hume_base_url: str = "https://api.hume.ai"
    hume_fixture_path: str = ""
    hume_evi_config_id: str = ""
    hume_evi_ws_url: str = "wss://api.hume.ai/v0/evi/chat"
    voice_mode: str = "pipeline"
    assemblyai_api_key_env: str = "ASSEMBLYAI_API_KEY"
    assemblyai_api_key_configured: bool = False
    deepgram_api_key_env: str = "DEEPGRAM_API_KEY"
    deepgram_api_key_configured: bool = False

    audio_cache_dir: str = "/private/tmp/voice-ai-companion/audio"
    orchestrator_public_base_url: str = "http://127.0.0.1:8765"

    def selected_providers(self) -> dict[str, str]:
        return {
            "stt": self.stt_provider_id,
            "llm": self.llm_provider_id,
            "tts": self.tts_provider_id,
            "voice_analysis": self.voice_analysis_provider_id,
        }


def load_runtime_config(env: Mapping[str, str] | None = None) -> ProviderRuntimeConfig:
    source = _source_env(env)

    elevenlabs_key_env = _env(source, "ELEVENLABS_API_KEY_ENV", "ELEVENLABS_API_KEY")
    hume_key_env = _env(source, "HUME_API_KEY_ENV", "HUME_API_KEY")
    assemblyai_key_env = _env(source, "ASSEMBLYAI_API_KEY_ENV", "ASSEMBLYAI_API_KEY")
    deepgram_key_env = _env(source, "DEEPGRAM_API_KEY_ENV", "DEEPGRAM_API_KEY")
    openai_key_env = _env(source, "OPENAI_API_KEY_ENV", "OPENAI_API_KEY")

    elevenlabs_api_key = _env(source, elevenlabs_key_env)
    openai_api_key = _env(source, openai_key_env)
    hume_api_key = _env(source, hume_key_env)
    hume_evi_config_id = _env(source, "HUME_EVI_CONFIG_ID", _env(source, "HUME_CONFIG_ID"))
    if elevenlabs_api_key:
        default_stt_provider = "elevenlabs_stt"
    elif openai_api_key:
        default_stt_provider = "openai_stt"
    else:
        default_stt_provider = "mock_stt"
    default_llm_provider = "openai_llm" if openai_api_key else "local_companion"
    elevenlabs_voice_id = _env(source, "ELEVENLABS_VOICE_ID")
    default_tts_provider = (
        "elevenlabs_tts" if elevenlabs_api_key and elevenlabs_voice_id else "mock_tts"
    )
    default_voice_mode = "pipeline"

    return ProviderRuntimeConfig(
        stt_provider_id=_env(source, "COMPANION_STT_PROVIDER", default_stt_provider),
        llm_provider_id=_env(source, "COMPANION_LLM_PROVIDER", default_llm_provider),
        tts_provider_id=_env(source, "COMPANION_TTS_PROVIDER", default_tts_provider),
        voice_analysis_provider_id=_env(
            source,
            "COMPANION_VOICE_ANALYSIS_PROVIDER",
            "local_voice_analysis",
        ),
        elevenlabs_api_key_env=elevenlabs_key_env,
        elevenlabs_api_key=elevenlabs_api_key,
        elevenlabs_api_key_configured=bool(elevenlabs_api_key),
        elevenlabs_voice_id=elevenlabs_voice_id,
        elevenlabs_model_id=_env(source, "ELEVENLABS_MODEL_ID", "eleven_flash_v2_5"),
        elevenlabs_base_url=_env(
            source,
            "ELEVENLABS_BASE_URL",
            "https://api.elevenlabs.io",
        ),
        elevenlabs_output_format=_env(
            source,
            "ELEVENLABS_OUTPUT_FORMAT",
            "pcm_24000",
        ),
        elevenlabs_language_code=_env(source, "ELEVENLABS_LANGUAGE_CODE", "uz"),
        elevenlabs_stt_model_id=_env(source, "ELEVENLABS_STT_MODEL_ID", "scribe_v2"),
        elevenlabs_stt_language_code=_env(source, "ELEVENLABS_STT_LANGUAGE_CODE", "uz"),
        kokoro_model_path=_env(source, "KOKORO_MODEL_PATH"),
        kokoro_voice_name=_env(source, "KOKORO_VOICE_NAME"),
        openai_api_key_env=openai_key_env,
        openai_api_key=openai_api_key,
        openai_api_key_configured=bool(openai_api_key),
        openai_base_url=_env(source, "OPENAI_BASE_URL", "https://api.openai.com"),
        openai_model=_env(source, "OPENAI_MODEL", "gpt-4o-mini"),
        openai_stt_model=_env(source, "OPENAI_STT_MODEL", "whisper-1"),
        openai_stt_language_code=_env(source, "OPENAI_STT_LANGUAGE_CODE", "uz"),
        hume_api_key_env=hume_key_env,
        hume_api_key=hume_api_key,
        hume_api_key_configured=bool(hume_api_key),
        hume_base_url=_env(source, "HUME_BASE_URL", "https://api.hume.ai"),
        hume_fixture_path=_env(source, "HUME_FIXTURE_PATH"),
        hume_evi_config_id=hume_evi_config_id,
        hume_evi_ws_url=_env(source, "HUME_EVI_WS_URL", "wss://api.hume.ai/v0/evi/chat"),
        voice_mode=_env(source, "COMPANION_VOICE_MODE", default_voice_mode),
        assemblyai_api_key_env=assemblyai_key_env,
        assemblyai_api_key_configured=bool(_env(source, assemblyai_key_env)),
        deepgram_api_key_env=deepgram_key_env,
        deepgram_api_key_configured=bool(_env(source, deepgram_key_env)),
        audio_cache_dir=_env(
            source,
            "COMPANION_AUDIO_CACHE_DIR",
            "/private/tmp/voice-ai-companion/audio",
        ),
        orchestrator_public_base_url=_env(
            source,
            "COMPANION_ORCHESTRATOR_PUBLIC_BASE_URL",
            "http://127.0.0.1:8765",
        ),
    )


def _source_env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is not None:
        return env
    env_file = Path(environ.get("COMPANION_ENV_FILE", _default_env_path()))
    values = _read_env_file(env_file)
    values.update(environ)
    return values


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".env"


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not name:
            continue
        values[name] = _strip_env_value(value)
    return values


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _env(source: Mapping[str, str], name: str, default: str = "") -> str:
    return source.get(name, default).strip()
