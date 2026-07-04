from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "services" / "orchestrator"
sys.path.insert(0, str(ROOT))

from companion_core.api import run_server  # noqa: E402
from companion_core.runtime import build_default_runtime  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local companion orchestrator.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run_server(build_default_runtime(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()

