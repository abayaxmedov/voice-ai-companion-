#!/usr/bin/env bash
# Ovozli Hamroh — serverda web rejimda ishga tushirish (Linux, stdlib-only).
# Foydalanish: bash deploy/server_run.sh
# UI: http://SERVER_IP:8765/?token=<TOKEN>  (token .env dagi COMPANION_API_TOKEN)
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null || { echo "python3 topilmadi"; exit 1; }
PYV=$(python3 -c 'import sys; print(sys.version_info[:2] >= (3, 10))')
[ "$PYV" = "True" ] || { echo "python3 >= 3.10 kerak"; exit 1; }

# .env tayyorlash (birinchi marta).
if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env yaratildi (.env.example dan)."
fi

# Linux uchun audio kesh yo'li (macOS'dagi /private/tmp o'rniga).
if grep -q "^COMPANION_AUDIO_CACHE_DIR=/private/tmp" .env; then
  sed -i "s|^COMPANION_AUDIO_CACHE_DIR=.*|COMPANION_AUDIO_CACHE_DIR=/tmp/voice-ai-companion/audio|" .env
fi

# Tashqi manzil: audio URL'lari brauzerga shu bazadan qaytadi.
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
IP=${IP:-127.0.0.1}
sed -i "s|^COMPANION_ORCHESTRATOR_PUBLIC_BASE_URL=.*|COMPANION_ORCHESTRATOR_PUBLIC_BASE_URL=http://${IP}:8765|" .env

# API token (ochiq portda majburiy himoya): yo'q bo'lsa yaratamiz.
if ! grep -q "^COMPANION_API_TOKEN=" .env; then
  TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))")
  printf "\n# Ochiq portda /voice/turn kabi endpointlar uchun token.\nCOMPANION_API_TOKEN=%s\n" "$TOKEN" >> .env
fi
TOKEN=$(grep "^COMPANION_API_TOKEN=" .env | cut -d= -f2)

# Eski jarayonni to'xtatib, yangisini fonda ishga tushiramiz.
pkill -f "run_orchestrator.py" 2>/dev/null || true
sleep 1
nohup python3 scripts/dev/run_orchestrator.py --host 0.0.0.0 --port 8765 \
  > orchestrator.log 2>&1 &
sleep 2

if curl -sf "http://127.0.0.1:8765/health" >/dev/null; then
  echo ""
  echo "================================================================"
  echo "  Ishga tushdi ✅"
  echo "  UI:      http://${IP}:8765/?token=${TOKEN}"
  echo "  Log:     tail -f orchestrator.log"
  echo "  To'xtatish: pkill -f run_orchestrator.py"
  echo "================================================================"
  if ! grep -q "^ELEVENLABS_API_KEY=..*" .env; then
    echo "  DIQQAT: hozircha MOCK rejim. Haqiqiy ovoz uchun .env da"
    echo "  ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, OPENAI_API_KEY hamda"
    echo "  COMPANION_STT_PROVIDER=elevenlabs_stt, COMPANION_LLM_PROVIDER=openai_llm,"
    echo "  COMPANION_TTS_PROVIDER=elevenlabs qiymatlarini kiriting, so'ng:"
    echo "  bash deploy/server_run.sh"
  fi
  echo "  Eslatma: token URL'siz UI ochiladi, lekin suhbat endpointlari 401 qaytaradi."
else
  echo "Ishga tushmadi — orchestrator.log ni tekshiring:"; tail -20 orchestrator.log; exit 1
fi
