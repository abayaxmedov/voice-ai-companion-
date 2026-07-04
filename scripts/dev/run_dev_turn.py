from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "services" / "orchestrator"
sys.path.insert(0, str(ROOT))

from companion_core.app import run_dev_turn  # noqa: E402


if __name__ == "__main__":
    transcript = " ".join(sys.argv[1:]) or "Salom, bugun Toshkentda ob-havo qanday?"
    print(json.dumps(run_dev_turn(transcript), ensure_ascii=False, indent=2))

