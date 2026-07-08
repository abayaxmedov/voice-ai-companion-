from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the local companion stack.")
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8770")
    parser.add_argument("--orchestrator-url", default="http://127.0.0.1:8765")
    parser.add_argument("--player-url", default="http://127.0.0.1:8888")
    parser.add_argument("--mark-stream-ready", action="store_true")
    args = parser.parse_args()

    if args.mark_stream_ready:
        post(
            f"{args.bridge_url}/avatar/ready",
            {"avatar_id": "metahuman_default", "player_url": args.player_url},
        )

    health = get(f"{args.orchestrator_url}/health")
    assert health["ready"] is True, health
    assert health["avatar_bridge"]["ready"] is True, health["avatar_bridge"]

    turn = post(
        f"{args.orchestrator_url}/voice/turn",
        {
            "session_id": "smoke-session",
            "agent_id": "default",
            "transcript_override": "Salom, ovozli avatar testini boshlaymiz.",
        },
    )
    assert turn["avatar_job"]["avatar_id"] == "metahuman_default", turn["avatar_job"]

    events = get(f"{args.bridge_url}/avatar/events")
    assert events["events"], events
    assert events["events"][-1]["type"] == "avatar.play", events

    print(
        json.dumps(
            {
                "ok": True,
                "bridge": health["avatar_bridge"],
                "turn_id": turn["turn_id"],
                "last_event": events["events"][-1]["type"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def get(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    # Real TTS/LLM provayderlar bilan turn 2.5s dan uzoq davom etadi.
    with urlopen(request, timeout=45.0) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
