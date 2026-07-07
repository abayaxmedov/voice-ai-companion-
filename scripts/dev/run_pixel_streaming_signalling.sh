#!/usr/bin/env bash
# Epic PixelStreamingInfrastructure signalling serverini (lokal) ishga tushiradi.
#
# Portlar: 80 (player HTTP) + 8888 (UE streamer) — bizning 8765/8770 bilan
# konflikt yo'q. macOS'da 80-portni oddiy foydalanuvchi ham ochadi.
#
# Birinchi ishga tushirishda repo clone qilinadi (~200MB) va npm install
# bo'ladi — internet kerak. Keyingi safarlar tez.
#
# Muhit o'zgaruvchilari:
#   PSI_DIR    — infra papkasi (sukut: <repo>/unreal/PixelStreamingInfrastructure)
#   PSI_BRANCH — git branch (sukut: UE5.8, topilmasa master)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSI_DIR="${PSI_DIR:-$ROOT_DIR/unreal/PixelStreamingInfrastructure}"
PSI_BRANCH="${PSI_BRANCH:-UE5.8}"
PSI_URL="https://github.com/EpicGamesExt/PixelStreamingInfrastructure.git"

if [ ! -d "$PSI_DIR" ]; then
  echo "[signalling] Clone: $PSI_URL ($PSI_BRANCH) -> $PSI_DIR"
  git clone --depth 1 --branch "$PSI_BRANCH" "$PSI_URL" "$PSI_DIR" \
    || { echo "[signalling] $PSI_BRANCH branch topilmadi, master olinadi"; \
         git clone --depth 1 "$PSI_URL" "$PSI_DIR"; }
fi

cd "$PSI_DIR/SignallingWebServer"

# Eski layout: tayyor bash skriptlar bilan.
if [ -x platform_scripts/bash/start.sh ]; then
  [ -x platform_scripts/bash/setup.sh ] && platform_scripts/bash/setup.sh || true
  exec platform_scripts/bash/start.sh "$@"
fi

# Yangi TypeScript layout (wilbur): npm bilan.
command -v node >/dev/null 2>&1 || { echo "Node.js kerak (>=18): brew install node"; exit 1; }
echo "[signalling] npm install/build (birinchi marta sekin bo'ladi)"
npm install
npm run build >/dev/null 2>&1 || true
exec npm start -- --serve "$@"
