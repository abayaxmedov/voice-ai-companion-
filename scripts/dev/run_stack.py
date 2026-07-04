from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local companion dev stack.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--bridge-port", type=int, default=8770)
    parser.add_argument("--orchestrator-port", type=int, default=8765)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--player-url", default="http://127.0.0.1:8888")
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    commands = [
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "run_avatar_bridge.py"),
            "--host",
            args.host,
            "--port",
            str(args.bridge_port),
            "--player-url",
            args.player_url,
        ],
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "run_orchestrator.py"),
            "--host",
            args.host,
            "--port",
            str(args.orchestrator_port),
        ],
        [
            sys.executable,
            str(ROOT / "scripts" / "dev" / "run_frontend.py"),
            "--host",
            args.host,
            "--port",
            str(args.frontend_port),
        ],
    ]

    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env))
            time.sleep(0.25)

        failed = [process for process in processes if process.poll() is not None]
        if failed:
            return max((process.returncode or 1) for process in failed)

        print(
            "\nLocal companion stack is running:\n"
            f"- Avatar bridge: http://{args.host}:{args.bridge_port}\n"
            f"- Orchestrator:   http://{args.host}:{args.orchestrator_port}\n"
            f"- Frontend:       http://{args.host}:{args.frontend_port}\n"
            f"- Pixel player:   {args.player_url}\n\n"
            "Press Ctrl-C to stop all services.",
            flush=True,
        )

        while all(process.poll() is None for process in processes):
            time.sleep(0.5)

        return max((process.returncode or 0) for process in processes)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        for process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
