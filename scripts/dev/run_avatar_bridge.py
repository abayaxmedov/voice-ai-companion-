from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "services" / "avatar-bridge"
sys.path.insert(0, str(ROOT))

from avatar_bridge.api import run_server  # noqa: E402
from avatar_bridge.runtime import MetaHumanBridgeRuntime  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local MetaHuman bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--player-url", default="http://127.0.0.1:8888")
    args = parser.parse_args()
    run_server(
        MetaHumanBridgeRuntime(player_url=args.player_url),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
