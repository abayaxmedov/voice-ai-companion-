from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

UTC = timezone.utc
import base64
import binascii
import mimetypes
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from companion_core.avatar_bridge import AvatarBridgeClient
from companion_core.config import (
    ProviderRuntimeConfig,
    _default_env_path,
    load_runtime_config,
)
from companion_core.contracts import (
    AgentProfile,
    AudioUploadResult,
    CachedAudioFile,
    ProviderHealth,
    RuntimeState,
    VoiceTurnRequest,
    VoiceTurnResult,
)
from companion_core.pipeline.voice_turn import PipelineProviderSelection, VoiceTurnPipeline
from companion_core.providers.factory import build_default_registry
from companion_core.storage.memory import (
    InMemoryAgentStore,
    apply_profile_overrides,
    default_agent,
    load_profile_overrides,
    save_profile_overrides,
)


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    state: RuntimeState
    message: str
    created_at: str


@dataclass
class RuntimeContext:
    selection: PipelineProviderSelection
    config: ProviderRuntimeConfig = field(default_factory=load_runtime_config)
    avatar_bridge: AvatarBridgeClient = field(default_factory=AvatarBridgeClient)
    state: RuntimeState = RuntimeState.BOOTING
    events: list[RuntimeEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.registry = build_default_registry(self.config)
        self.agent_store = InMemoryAgentStore()
        agent = apply_profile_overrides(
            default_agent(), load_profile_overrides(self._profile_path())
        )
        self.agent_store.add(agent)
        self.history: list[dict[str, object]] = []
        self.pipeline = VoiceTurnPipeline(self.registry, self.selection)
        self.set_state(RuntimeState.IDLE, "Runtime initialized.")

    @staticmethod
    def _profile_path() -> Path:
        return _default_env_path().parent / ".companion_profile.json"

    def set_state(self, state: RuntimeState, message: str) -> None:
        self.state = state
        self.events.append(
            RuntimeEvent(
                event_id=str(uuid4()),
                state=state,
                message=message,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        self.events = self.events[-50:]

    def health(self) -> dict[str, object]:
        providers = self.provider_health()
        ready = all(item.ready for item in providers)
        return {
            "service": "orchestrator",
            "ready": ready,
            "state": self.state,
            "providers": providers,
            "selected_providers": self.config.selected_providers(),
            "voice_mode": self.config.voice_mode,
            "hume_evi": self.hume_evi_status(),
            "avatar_bridge": self.avatar_bridge.health(),
            "agents": list(self.agent_store.agents.values()),
        }

    def provider_health(self) -> list[ProviderHealth]:
        selected = self.selection
        return [
            self.registry.require_stt(selected.stt_provider_id).health(),
            self.registry.require_llm(selected.llm_provider_id).health(),
            self.registry.require_tts(selected.tts_provider_id).health(),
            self.registry.require_voice_analysis(selected.voice_analysis_provider_id).health(),
        ]

    def provider_catalog(self) -> dict[str, object]:
        return {
            "selected": self.config.selected_providers(),
            "providers": self.registry.all_health(),
            "voice_mode": self.config.voice_mode,
            "hume_evi": self.hume_evi_status(),
        }

    def hume_evi_status(self) -> dict[str, object]:
        ready = bool(self.config.hume_api_key and self.config.hume_evi_config_id)
        missing: list[str] = []
        if not self.config.hume_api_key:
            missing.append(self.config.hume_api_key_env)
        if not self.config.hume_evi_config_id:
            missing.append("HUME_EVI_CONFIG_ID")
        return {
            "ready": ready,
            "selected": self.config.voice_mode == "hume_evi",
            "status": "configured" if ready else "missing_config",
            "missing": missing,
        }

    def runtime_state(self) -> dict[str, object]:
        return {
            "state": self.state,
            "events": self.events,
            "active_agent_id": "default",
            "avatar_bridge": self.avatar_bridge.health(),
        }

    def agents(self) -> list[AgentProfile]:
        return list(self.agent_store.agents.values())

    def save_audio_upload(self, audio_base64: str, mime_type: str, session_id: str) -> AudioUploadResult:
        if not audio_base64.strip():
            raise ValueError("audio_base64 is required.")
        clean_base64 = _strip_data_url_prefix(audio_base64)
        try:
            audio_bytes = base64.b64decode(clean_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("audio_base64 is not valid base64.") from exc
        if not audio_bytes:
            raise ValueError("Uploaded audio is empty.")
        max_size = 25 * 1024 * 1024
        if len(audio_bytes) > max_size:
            raise ValueError("Uploaded audio is larger than 25 MiB.")

        safe_session = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))[:80]
        if not safe_session:
            safe_session = "session"
        extension = _extension_for_mime(mime_type)
        cache_dir = Path(self.config.audio_cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{safe_session}-{uuid4()}{extension}"
        cache_path.write_bytes(audio_bytes)
        return AudioUploadResult(
            audio_ref=f"file://{cache_path}",
            mime_type=mime_type,
            size_bytes=len(audio_bytes),
            cache_path=str(cache_path),
        )

    def run_voice_turn(self, request: VoiceTurnRequest):
        agent = self.agent_store.require(request.agent_id)
        self.set_state(RuntimeState.LISTENING, "Voice turn accepted.")
        try:
            self.set_state(RuntimeState.THINKING, "Voice turn processing.")
            result = self.pipeline.run(request, agent, history=self.recent_history())
            self._append_history(result)
            result = self._with_public_audio_ref(result)
            try:
                bridge_event = self.avatar_bridge.send_playback(result.avatar_job)
                self.set_state(
                    RuntimeState.SPEAKING,
                    f"MetaHuman bridge accepted playback event {bridge_event.get('id')}.",
                )
            except Exception as exc:  # noqa: BLE001 - voice turn should still return in dev mode.
                self.set_state(
                    RuntimeState.SPEAKING,
                    f"Avatar playback job created; bridge unavailable: {exc}",
                )
            return result
        except Exception:
            self.set_state(RuntimeState.ERROR, "Voice turn failed.")
            raise
        finally:
            if self.state == RuntimeState.SPEAKING:
                self.set_state(RuntimeState.IDLE, "Runtime ready.")

    def run_voice_turn_stream(self, request: VoiceTurnRequest, emit) -> VoiceTurnResult:
        """Streaming turn: meta/audio hodisalari emit orqali, yakunda 'end'.

        Provayder streaming'ni qo'llamasa StreamingUnsupported ko'tariladi
        (hech narsa emit qilinmagan bo'ladi) — chaqiruvchi klassik yo'lga
        qaytishi mumkin.
        """
        agent = self.agent_store.require(request.agent_id)
        self.set_state(RuntimeState.LISTENING, "Voice turn accepted (stream).")
        try:
            self.set_state(RuntimeState.THINKING, "Voice turn processing (stream).")
            result = self.pipeline.run_streaming(
                request, agent, self.recent_history(), emit
            )
            self._append_history(result)
            result = self._with_public_audio_ref(result)
            try:
                self.avatar_bridge.send_playback(result.avatar_job)
            except Exception:  # noqa: BLE001 - bridge ixtiyoriy (dev rejim).
                pass
            self.set_state(RuntimeState.SPEAKING, "Streaming playback under way.")
            emit(
                {
                    "type": "end",
                    "turn_id": result.turn_id,
                    "audio_ref": result.tts.audio_ref,
                    "duration_ms": result.tts.duration_ms,
                    "latency_ms": result.latency_ms,
                }
            )
            return result
        except Exception:
            self.set_state(RuntimeState.ERROR, "Streaming voice turn failed.")
            raise
        finally:
            if self.state == RuntimeState.SPEAKING:
                self.set_state(RuntimeState.IDLE, "Runtime ready.")

    def _append_history(self, result: VoiceTurnResult) -> None:
        now = datetime.now(UTC).isoformat()
        user_text = result.transcript.text.strip()
        if user_text:
            self.history.append(
                {"role": "user", "text": user_text, "created_at": now}
            )
        self.history.append(
            {
                "role": "assistant",
                "text": result.llm_response.response,
                "mood": result.llm_response.mood,
                "created_at": now,
            }
        )
        self.history = self.history[-80:]

    def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
        """Recent turns as chat messages for LLM context."""
        messages: list[dict[str, str]] = []
        for item in self.history[-limit:]:
            role = "assistant" if item.get("role") == "assistant" else "user"
            text = str(item.get("text", "")).strip()
            if text:
                messages.append({"role": role, "content": text})
        return messages

    def conversation(self) -> dict[str, object]:
        return {"messages": list(self.history)}

    def clear_conversation(self) -> dict[str, object]:
        self.history = []
        return {"messages": []}

    def profile(self) -> dict[str, object]:
        agent = self.agent_store.require("default")
        return {
            "agent_id": agent.agent_id,
            "display_name": agent.display_name,
            "persona": agent.persona,
            "user_name": agent.user_name,
            "city": agent.city,
            "timezone": agent.timezone,
            "vibe_formality": agent.vibe_formality,
            "vibe_humor": agent.vibe_humor,
            "vibe_directness": agent.vibe_directness,
            "vibe_verbosity": agent.vibe_verbosity,
            "hobbies": list(agent.hobbies),
            "language": agent.language,
        }

    def update_profile(self, payload: dict[str, object]) -> dict[str, object]:
        agent = apply_profile_overrides(self.agent_store.require("default"), payload)
        self.agent_store.add(agent)
        save_profile_overrides(self._profile_path(), agent)
        return self.profile()

    def settings(self) -> dict[str, object]:
        """Redacted settings view. Raw API keys are never returned."""
        return {
            "selected_providers": self.config.selected_providers(),
            "openai": {
                "api_key_configured": self.config.openai_api_key_configured,
                "model": self.config.openai_model,
                "stt_model": self.config.openai_stt_model,
            },
            "elevenlabs": {
                "api_key_configured": self.config.elevenlabs_api_key_configured,
                "voice_id": self.config.elevenlabs_voice_id,
                "model_id": self.config.elevenlabs_model_id,
            },
            "aisha": {
                "api_key_configured": self.config.aisha_api_key_configured,
                "model": self.config.aisha_tts_model,
                "mood": self.config.aisha_tts_mood,
                "voice_id": self.config.aisha_voice_id,
            },
            "voice_mode": self.config.voice_mode,
        }

    _SETTINGS_ENV_KEYS = {
        "openai_api_key": "OPENAI_API_KEY",
        "openai_model": "OPENAI_MODEL",
        "elevenlabs_api_key": "ELEVENLABS_API_KEY",
        "elevenlabs_voice_id": "ELEVENLABS_VOICE_ID",
        "elevenlabs_model_id": "ELEVENLABS_MODEL_ID",
        "aisha_api_key": "AISHA_API_KEY",
        "aisha_tts_mood": "AISHA_TTS_MOOD",
        "aisha_voice_id": "AISHA_VOICE_ID",
        "aisha_tts_speed": "AISHA_TTS_SPEED",
        "elevenlabs_speed": "ELEVENLABS_SPEED",
        "stt_provider": "COMPANION_STT_PROVIDER",
        "llm_provider": "COMPANION_LLM_PROVIDER",
        "tts_provider": "COMPANION_TTS_PROVIDER",
        "voice_analysis_provider": "COMPANION_VOICE_ANALYSIS_PROVIDER",
    }

    def update_settings(self, payload: dict[str, object]) -> dict[str, object]:
        """Persist provider settings to the local .env file and hot-reload providers."""
        updates: dict[str, str] = {}
        for field_name, env_name in self._SETTINGS_ENV_KEYS.items():
            if field_name in payload:
                value = str(payload[field_name] or "").strip()
                updates[env_name] = value
        if not updates:
            raise ValueError("No supported settings fields were provided.")

        _write_env_updates(_default_env_path(), updates)
        self.reload_config()
        return self.settings()

    def reload_config(self) -> None:
        self.config = load_runtime_config()
        self.selection = PipelineProviderSelection(
            stt_provider_id=self.config.stt_provider_id,
            llm_provider_id=self.config.llm_provider_id,
            tts_provider_id=self.config.tts_provider_id,
            voice_analysis_provider_id=self.config.voice_analysis_provider_id,
        )
        self.registry = build_default_registry(self.config)
        self.pipeline = VoiceTurnPipeline(self.registry, self.selection)
        self.set_state(RuntimeState.IDLE, "Provider settings reloaded.")

    def public_audio_ref(self, audio_ref: str) -> str:
        if not audio_ref.startswith("file://"):
            return audio_ref
        path = Path(audio_ref.removeprefix("file://")).expanduser()
        if not self._is_in_audio_cache(path):
            return audio_ref
        base_url = self.config.orchestrator_public_base_url.rstrip("/")
        return f"{base_url}/audio/cache/{quote(path.name)}"

    def read_cached_audio(self, filename: str) -> CachedAudioFile:
        if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
            raise ValueError("Invalid audio filename.")
        cache_root = Path(self.config.audio_cache_dir).expanduser().resolve()
        path = (cache_root / filename).resolve()
        if not _is_relative_to(path, cache_root):
            raise ValueError("Audio path is outside the cache directory.")
        if not path.is_file():
            raise FileNotFoundError("Audio file was not found.")
        return CachedAudioFile(
            filename=path.name,
            mime_type=_mime_type_for_audio(path),
            content=path.read_bytes(),
        )

    def _with_public_audio_ref(self, result: VoiceTurnResult) -> VoiceTurnResult:
        audio_ref = self.public_audio_ref(result.tts.audio_ref)
        if audio_ref == result.tts.audio_ref:
            return result
        return replace(
            result,
            tts=replace(result.tts, audio_ref=audio_ref),
            avatar_job=replace(result.avatar_job, audio_ref=audio_ref),
        )

    def _is_in_audio_cache(self, path: Path) -> bool:
        cache_root = Path(self.config.audio_cache_dir).expanduser().resolve()
        try:
            resolved = path.resolve(strict=False)
        except RuntimeError:
            return False
        return _is_relative_to(resolved, cache_root)


def build_default_runtime(config: ProviderRuntimeConfig | None = None) -> RuntimeContext:
    config = config or load_runtime_config()
    selection = PipelineProviderSelection(
        stt_provider_id=config.stt_provider_id,
        llm_provider_id=config.llm_provider_id,
        tts_provider_id=config.tts_provider_id,
        voice_analysis_provider_id=config.voice_analysis_provider_id,
    )
    return RuntimeContext(selection=selection, config=config)


def _write_env_updates(env_path: Path, updates: dict[str, str]) -> None:
    """Merge key=value updates into the local .env file.

    Empty values remove the key so config defaults apply again. The file stays
    local-only; values are never logged.
    """
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            rewritten.append(line)
            continue
        name = stripped.split("=", 1)[0].strip()
        if name in remaining:
            value = remaining.pop(name)
            if value:
                rewritten.append(f"{name}={value}")
            # Empty value: drop the line entirely.
            continue
        rewritten.append(line)

    for name, value in remaining.items():
        if value:
            rewritten.append(f"{name}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(rewritten).rstrip("\n") + "\n", encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass


def _strip_data_url_prefix(value: str) -> str:
    if "," in value and value.strip().lower().startswith("data:"):
        return value.split(",", 1)[1]
    return value.strip()


def _extension_for_mime(mime_type: str) -> str:
    normalized = mime_type.split(";", 1)[0].strip().lower()
    return {
        "audio/webm": ".webm",
        "audio/webm;codecs=opus": ".webm",
        "audio/mp4": ".m4a",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/ogg": ".ogg",
    }.get(normalized, ".audio")


def _mime_type_for_audio(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
