#!/usr/bin/env bash
# Butun lokal stackni BITTA buyruq bilan ko'taradi:
#   1) signalling server (80 player + 8888 streamer) — birinchi safar clone+npm
#   2) orchestrator (8765) + avatar bridge (8770)
#   3) Unreal MetaHuman stream (-game; HEADLESS=1 bo'lsa oynasiz)
#
#   scripts/dev/run_full_stack.sh            # hammasi
#   NO_UNREAL=1 scripts/dev/run_full_stack.sh  # UE'siz (yengil)
#
# To'xtatish: Ctrl+C — barcha bolalar ham to'xtaydi.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIDS=()

cleanup() {
  echo; echo "[full-stack] to'xtatilmoqda..."
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[full-stack] 1/3 signalling server (80 + 8888)"
"$ROOT_DIR/scripts/dev/run_pixel_streaming_signalling.sh" &
PIDS+=($!)

echo "[full-stack] 2/3 orchestrator (8765) + bridge (8770)"
python3 "$ROOT_DIR/scripts/dev/run_stack.py" &
PIDS+=($!)

# Backend tayyor bo'lishini kutamiz.
for _ in $(seq 1 30); do
  curl -s --max-time 1 http://127.0.0.1:8770/avatar/status >/dev/null 2>&1 && break
  sleep 1
done

if [ "${NO_UNREAL:-0}" != "1" ]; then
  echo "[full-stack] 3/3 Unreal MetaHuman stream (og'ir qadam, 2-4 daqiqa)"
  "$ROOT_DIR/scripts/dev/run_unreal_stream.sh" &
  PIDS+=($!)
else
  echo "[full-stack] 3/3 UE o'tkazib yuborildi (NO_UNREAL=1)"
fi

echo "[full-stack] tayyor: Electron/web http://127.0.0.1:8765 | player http://127.0.0.1:80"
wait