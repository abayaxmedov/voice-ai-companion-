#!/usr/bin/env bash
# CompanionAvatar'ni editorsiz -game rejimida, Pixel Streaming bilan ishga
# tushiradi. Oldin signalling server ishlashi kerak:
#   scripts/dev/run_pixel_streaming_signalling.sh
# va python stack:
#   python3 scripts/dev/run_stack.py
#
# Muhit o'zgaruvchilari:
#   UE_ROOT    — engine yo'li (sukut: /Users/Shared/Epic Games/UE_5.8)
#   SIGNAL_URL — signalling ws manzili (sukut: ws://127.0.0.1:8888)
#   HEADLESS=1 — oynasiz render (kamroq issiqlik); stream baribir ishlaydi
#   RES        — oyna o'lchami (sukut: 1280x720)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UE_ROOT="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
UPROJECT="$ROOT_DIR/unreal/CompanionAvatar/CompanionAvatar.uproject"
SIGNAL_URL="${SIGNAL_URL:-ws://127.0.0.1:8888}"
RES="${RES:-1280x720}"
RES_X="${RES%x*}"; RES_Y="${RES#*x}"

ARGS=(
  "$UPROJECT" -game
  -ResX="$RES_X" -ResY="$RES_Y" -windowed
  # ConnectionURL DefaultGame.ini'da ham bor; launch-param ustunlik qiladi.
  # Diqqat: -PixelStreamingURL (v1) atayin YO'Q — legacy plugin o'chirilgan,
  # bitta signalling serverga ikkita streamer ulanib qolmasin.
  -PixelStreamingConnectionURL="$SIGNAL_URL"
)
[ "${HEADLESS:-0}" = "1" ] && ARGS+=(-RenderOffscreen)

echo "[unreal] Stream -> $SIGNAL_URL (player: http://127.0.0.1:80)"
exec nice -n 5 "$UE_ROOT/Engine/Binaries/Mac/UnrealEditor" "${ARGS[@]}"
