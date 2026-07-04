from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path

from companion_core.contracts import AgentProfile

# Fields that may be overridden from the local profile file / PATCH /profile.
PROFILE_FIELDS = (
    "display_name",
    "persona",
    "user_name",
    "city",
    "timezone",
    "vibe_formality",
    "vibe_humor",
    "vibe_directness",
    "vibe_verbosity",
    "hobbies",
)

_FLOAT_FIELDS = {"vibe_formality", "vibe_humor", "vibe_directness", "vibe_verbosity"}
_STR_FIELDS = {"display_name", "persona", "user_name", "city", "timezone"}


@dataclass
class InMemoryAgentStore:
    agents: dict[str, AgentProfile] = field(default_factory=dict)

    def add(self, agent: AgentProfile) -> None:
        self.agents[agent.agent_id] = agent

    def require(self, agent_id: str) -> AgentProfile:
        return self.agents[agent_id]


def default_agent() -> AgentProfile:
    return AgentProfile(
        agent_id="default",
        display_name="Hamroh",
        avatar_id="metahuman_default",
        voice_profile_id="uzbek_default",
        enabled_tools=("web_search", "weather", "reminders"),
        city="Tashkent",
        timezone="Asia/Tashkent",
    )


def sanitize_profile_updates(payload: dict[str, object]) -> dict[str, object]:
    """Validate and coerce a raw payload into AgentProfile override kwargs."""
    updates: dict[str, object] = {}
    for name in PROFILE_FIELDS:
        if name not in payload:
            continue
        value = payload[name]
        if name in _FLOAT_FIELDS:
            try:
                number = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            updates[name] = max(0.0, min(1.0, number))
        elif name in _STR_FIELDS:
            updates[name] = str(value or "").strip()[:200]
        elif name == "hobbies":
            if isinstance(value, str):
                items = [part.strip() for part in value.split(",")]
            elif isinstance(value, (list, tuple)):
                items = [str(part).strip() for part in value]
            else:
                items = []
            updates[name] = tuple(item[:40] for item in items if item)[:16]
    return updates


def apply_profile_overrides(agent: AgentProfile, overrides: dict[str, object]) -> AgentProfile:
    updates = sanitize_profile_updates(overrides)
    if not updates:
        return agent
    return replace(agent, **updates)


def load_profile_overrides(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_profile_overrides(path: Path, agent: AgentProfile) -> None:
    data = {
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
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
