# Ovozli Hamroh — Desktop App (Electron)

O'zbek tilida faqat ovoz orqali ishlaydigan AI hamroh. Chat UI yo'q —
mikrofon tugmasi, animatsion avatar va diagnostika/sozlamalar panellari.

## Ishga tushirish

Talablar: macOS, Node.js 18+, Python 3.11+.

```bash
cd apps/desktop
npm install
npm start
```

Electron o'zi Python backendni (orchestrator 8765 + avatar bridge 8770)
ishga tushiradi va tayyor bo'lguncha kutadi.

## Web rejimi (Electronsiz, brauzerda)

Xuddi shu ilova brauzerda ham ishlaydi. Backendni ishga tushiring:

```bash
python3 scripts/dev/run_orchestrator.py
```

Keyin Chrome/Safari da oching: **http://127.0.0.1:8765**

Mikrofon localhost'da ruxsat so'raydi va ishlaydi. Hamma funksiya bir xil
(doimiy tinglash, suhbat, sozlamalar). Eslatma: bu lokal web — kalitlar
kompyuterdan chiqmaydi. Internetga chiqarish (domen, HTTPS, avtorizatsiya)
alohida bosqich.

## API kalitlari

Ilova ichida ⚙ (Sozlamalar) panelidan kiriting:

- OpenAI API kaliti — LLM (aql) va Whisper STT uchun
- ElevenLabs API kaliti + voice_id — STT (Scribe) va O'zbek TTS uchun

Kalitlar faqat lokal `.env` faylga (repo ildizida, 0600 ruxsat) yoziladi,
hech qaerga yuborilmaydi va API javoblarida qaytarilmaydi.

`.env` orqali qo'lda ham berish mumkin:

```bash
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=xi-...
ELEVENLABS_VOICE_ID=...
```

Kalitlar mavjud bo'lsa provayderlar avtomatik tanlanadi:
ElevenLabs STT → OpenAI Whisper → mock; OpenAI LLM → lokal mock;
ElevenLabs TTS (voice_id bilan) → mock.

## Foydalanish (Unclaw-uslub tajriba)

- **Doimiy tinglash:** pastki paneldagi to'lqin tugmasini yoqing — panel
  qizil yonadi, tugma bosmasdan shunchaki gapirasiz (VAD). Javob paytida
  gapirsangiz — barge-in: ijro darhol to'xtaydi.
- **Push-to-talk:** mikrofon tugmasini yoki Space ni bosib turib gapirish.
- **Matn:** pastki qatorga yozib Enter (Unclaw kabi qo'shimcha rejim).
- Salomlashuv, soat va iqtiboslar — chap yuqorida; agent ismi pastda.
- 🗨 — suhbat tarixi (bubbles); ⌗ (chap panel) — diagnostika; 🔔 —
  bildirishnomalar; ☁ — ob-havo (open-meteo, shahar profildan olinadi).
- ⚙ — sozlamalar: Profil (ismlar, shahar, vaqt zonasi, muloqot uslubi
  slayderlari, qiziqishlar — hammasi LLM promptiga ulanadi), Suhbat (LLM,
  OpenAI kalit/model), Ovoz (TTS/STT, ElevenLabs), Avatar, Haqida.
- Suhbat tarixi LLMga kontekst sifatida uzatiladi (oxirgi 12 xabar).

## Avatar

Unreal MacBookga o'rnatilmagani uchun ikki bosqichli yechim:

1. **3D realistik avatar (standart):** Three.js + Ready Player Me GLB,
   to'liq ARKit blendshape to'plami (jaw/mouth/brow/eye). Lab-sinxron
   backend qaytaradigan **viseme timeline**dan (fonema-aniq; ElevenLabs
   character-timestamps yoki o'zbekcha grafema→viseme fallback), amplituda
   faqat energiya modulyatori. Jonlilik: nigoh saccade'lari, asimmetrik
   ko'z qisish, gapirganda bosh ta'kidlari, ko'krakda nafas. Yoritish
   Unclaw uslubida: iliq key + sovuq fill + orqadan qizil rim, ACES tone
   mapping, yumshoq soya; kadr ko'krakdan yuqori, kamera biroz pastdan,
   fon qora-qizil radial gradient. Kayfiyat (mood) 300ms lerp bilan yuz
   ifodasiga o'tadi. FPS diagnostika panelida (maqsad: 55+).
   Sozlamalar → Avatar bo'limida o'z GLB manzilingizni qo'yishingiz mumkin
   (readyplayer.me da bepul avatar yasab, URL oxiriga
   `?morphTargets=ARKit` qo'shing; qo'shilmasa avtomatik qo'shiladi).
   Tez vizual test: `apps/desktop/renderer/avatar3d-preview.html`
   (lokal server orqali oching, masalan `python3 -m http.server`).
2. **2D placeholder (fallback):** internet bo'lmasa avtomatik ishlaydi.

Yakuniy maqsad — Unreal/MetaHuman (Pixel Streaming); bridge (8770) tayyor.

## Serverda (web rejim)

Orchestrator UI'ni o'zi ham beradi — serverda Electron shart emas:

```
git clone https://github.com/abayaxmedov/voice-ai-companion.git
cd voice-ai-companion
bash deploy/server_run.sh
```

Skript: `.env` yaratadi (Linux yo'llari bilan), tashqi IP'ni aniqlaydi,
`COMPANION_API_TOKEN` yaratadi va `0.0.0.0:8765` da ishga tushiradi.
UI: `http://SERVER_IP:8765/?token=TOKEN` (token skript chiqishida).
Haqiqiy ovoz uchun `.env` ga ElevenLabs/OpenAI kalitlarini kiritib skriptni
qayta ishga tushiring. Doimiy ishlashi uchun: `deploy/companion.service`.

Diqqat: ochiq portda token suhbat endpointlarini himoya qiladi, lekin trafik
oddiy HTTP — jiddiy foydalanish uchun reverse-proxy (Caddy/Nginx + TLS) qo'ying.
