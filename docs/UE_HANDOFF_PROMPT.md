# Code (Fable 5) uchun davom ettirish prompti — Unreal MetaHuman qismi

> Buni Code bo'limidagi Claude'ga (Fable 5) to'liq nusxalab bering.

---

Sen `/Users/user/projects/ai_model` repozitoriysida ishlaysan. Bu "Ovozli Hamroh" —
o'zbek tilida, faqat ovozli AI hamroh (Unclaw / fotonLabs Grace uslubida). Loyihaning
Python backend, Electron/web frontend va Three.js avatar qismlari **tayyor va ishlaydi**.
Hozir faqat **Unreal Engine MetaHuman + Pixel Streaming** qismini oxiriga yetkazish qoldi.

MUHIM QOIDA: bu muhitda Unreal Editor GUI'sini boshqarib bo'lmaydi (menyu, viewport,
Blueprint graf). Shuning uchun qolgan ishni **imkon qadar C++ va config (.ini) fayllar
bilan** hal qil — Blueprint/AnimGraph'da qo'lda qilinadigan minimal qadamlarni esa
foydalanuvchiga aniq yo'riqnoma sifatida yozib ber (u o'zi bajaradi).

## Hozirgi holat (nima tayyor)

Backend/Frontend (to'liq ishlaydi, tegma, faqat zarurat bo'lsa):
- `services/orchestrator` (:8765) — STT/LLM/TTS pipeline. Provayderlar: ElevenLabs,
  OpenAI, **Aisha** (aisha.group, o'zbekcha STT/TTS), mock. TTS tezligi `.env`da
  `AISHA_TTS_SPEED` / `ELEVENLABS_SPEED`.
- `services/avatar-bridge` (:8770) — MetaHuman ko'prigi. `/avatar/events` (poll),
  `/avatar/ready` (player_url qabul qiladi), `/avatar/status`.
- `apps/desktop` — Electron + web (backend `/` da statik beradi, http://127.0.0.1:8765).
  `renderer/app.js` ichidagi `updateAvatarStream()` allaqachon `/health` dagi
  `avatar_bridge.stream_ready` + `player_url` ni kuzatadi va UE Pixel Streaming
  oqimi tayyor bo'lsa Three.js avatar o'rnida `<iframe>` player ochadi, oqim
  uzilsa Three.js'ga qaytadi. **Ya'ni Electron tomoni tayyor.**
- Three.js avatar (`renderer/avatar3d.js`) — ko'zoynakli qiz (RPM GLB), lokal
  `assets/avatars/brunette.glb` dan yuklanadi. Kundalik ishlaydigan avatar shu.

Unreal (`unreal/CompanionAvatar/`, UE 5.8 Mac / 5.7 Windows):
- C++ modul (`Source/CompanionAvatar/`) — **build bo'ladi va tayyor**:
  - `CompanionBridgePoller` — :8770 bridge'ga BeginPlay'da `ready` yuboradi, hodisa
    poll qiladi, `OnAvatarPlayJob`/`OnAvatarPlayEvent`/`OnAvatarInterruptEvent`/
    `OnAvatarStateEvent` (BlueprintImplementableEvent) fire qiladi.
  - `CompanionLipSync` — viseme+curve fuziyasi, koartikulyatsiya, mood lerp,
    prosodiya→qosh; `GetCurveValue("jawOpen")` va h.k. beradi (ARKit nomlari).
  - `CompanionDirector` (AActor) — ichida `BridgePoller` bor; BeginPlay'da sahnadagi
    birinchi `ACineCameraActor`ga **view target**ni o'tkazadi
    (`bAutoViewTargetToCineCamera=true`). Ya'ni Pixel Streaming aynan shu kamerani
    oqimlaydi.
- MetaHuman belgi yig'ilgan: `Content/MetaHumans/NewMetaHumanCharacter/BP_NewMetaHumanCharacter`.
- Sahna saqlangan: `Content/CompanionStage` (level). Aktyorlar (5 ta):
  - `BP_NewMetaHumanCharacter` — (0,0,0)
  - `CineCameraActor` — Location (220, 0, 145), Rotation Yaw 180, 35mm, 16:9
  - `DirectionalLight` — 40 lux
  - `SkyLight`
  - `PointLight` — qizil rim, Location (-90, 35, 175), 60 cd, rang ~ (1.0, 0.23, 0.25)
- Konfig: `Config/DefaultEngine.ini` da `[/Script/PixelStreaming.PixelStreamingSettings]`
  bo'limi bor.

Ya'ni sahna, yoritish (Unclaw qizil rim), kamera va view-target/bridge C++ tayyor.

## Qolgan ish (bosqichma-bosqich)

### 1. Director'ni sahnaga qo'yish (view target + bridge ulanishi)
`ACompanionDirector` sahnada bo'lsa — view target avtomatik CineCamera'ga o'tadi va
poller bridge'ga ulanadi. Buni **kod bilan kafolatlab** ber:
- Variant A (tavsiya): `CompanionStage` levelida Director bo'lmasa, uni qo'shishni
  osonlashtir — masalan `AGameModeBase` subclass (`ACompanionGameMode`) yozib,
  `DefaultGameMode`ni shunga qo'y (`Config/DefaultEngine.ini` yoki World Settings),
  u BeginPlay'da `ACompanionDirector`ni `SpawnActor` qilsin (agar sahnada yo'q bo'lsa).
  Shunda foydalanuvchi hech narsa qo'ymasa ham ishlaydi.
- Variant B: foydalanuvchiga bitta qadam yoz — Place Actors'dan `CompanionDirector`ni
  `CompanionStage`ga sudrab tashlab, levelni saqlash.

### 2. Lab-sinxronni MetaHuman yuziga ulash
`CompanionLipSync`ni `BP_NewMetaHumanCharacter`ga ulash kerak. Iloji boricha C++'da:
- `CompanionDirector` (yoki yangi komponent) BeginPlay'da sahnadagi MetaHuman actor'ni
  topib, unga `UCompanionLipSync` komponentini runtime'da qo'shsin va poller'ning
  `OnAvatarPlayJob`ini LipSync'ning `StartJob(...)`iga C++'da bog'lasin (delegate).
  Shunda Blueprint event-graf shart emas.
- Faqat **Face AnimBP** ichidagi "Modify Curve" tugunlari qo'lda qilinadi (AnimGraph
  GUI). Buning uchun aniq yo'riqnoma yoz: har ARKit curve (`jawOpen`, `mouthFunnel`,
  `mouthPucker`, `browInnerUp`, `mouthSmileLeft/Right`, ...) uchun
  `LipSync.GetCurveValue("...")` → Modify Curve. To'liq curve ro'yxati
  `CompanionLipSync.h` izohida. `Docs/UNREAL_SETUP.md` 7-bosqich.

### 3. Pixel Streaming (lokal)
- `Config/DefaultEngine.ini` da PixelStreaming2 sozlamalarini to'g'rila (macOS:
  VideoToolbox enkoder avtomatik).
- Signalling server uchun `scripts/dev/` ga skript yoz (Epic'ning
  PixelStreamingInfrastructure `SignallingWebServer`ini clone qilib ishga tushiradigan),
  yoki UE ichidagi o'rnatilgan signalling'ni yoq. Portlar: 8765/8770 band — konflikt yo'q.
- Launch param: `-PixelStreaming2SignallingURL=ws://127.0.0.1:8888` (yoki tegishlisi).
- `CompanionBridgePoller`ning `PlayerUrl` xossasini haqiqiy player manziliga to'g'rila;
  u `OnAvatarReadyEvent`da bridge'ga (`/avatar/ready`) yuboradi → Electron avtomatik
  o'sha oqimga o'tadi.

### 4. Test (mock bilan, kalitsiz)
- `python3 scripts/dev/run_stack.py` (orchestrator + bridge).
- UE'ni Standalone/PIE'da Pixel Streaming bilan ishga tushir.
- Web/Electron'dan matn yubor → bridge'da `avatar.play` ko'rinsin → UE'da lablar
  qimirlasin → Electron oynasida UE oqimi ochilsin. `curl 127.0.0.1:8770/avatar/status`.

## Muhim fayllar
- `unreal/CompanionAvatar/Docs/UNREAL_SETUP.md` — 0–10 bosqichli to'liq yo'l xaritasi.
- `unreal/CompanionAvatar/Docs/EVENT_CONTRACT.md` — bridge hodisa JSON formati.
- `unreal/CompanionAvatar/Source/CompanionAvatar/` — C++ (Director, Poller, LipSync).
- `services/avatar-bridge/avatar_bridge/` — bridge (:8770).
- `apps/desktop/renderer/app.js` — `updateAvatarStream()` (UE oqimiga avto-almashinuv).
- `docs/DECISIONS.md` — arxitektura qarorlari (AD-002: UE yakuniy avatar, Three.js oraliq).

## Cheklovlar / eslatmalar
- Foydalanuvchining Mac'i ~8GB RAM — MetaHuman yig'ish/PIE og'ir. Og'ir qadamlarni
  ogohlantir; Windows PC (ko'proq RAM/GPU) muqobil.
- UE 5.7 (Windows) va 5.8 (Mac) — assetlar yangi versiyada saqlansa eskida ochilmaydi.
  Target'lar `BuildSettingsVersion.Latest` (mos).
- Har C++ o'zgarishdan keyin modulni qayta build qil (UE editor "rebuild" yoki
  `Build.sh`/xcodebuild). Blueprint minimal — logikani C++'ga surishga harakat qil.
- Kalitlar `.env`da (git'ga kirmaydi): OPENAI_API_KEY, ELEVENLABS_API_KEY+VOICE_ID,
  AISHA_API_KEY. Bularni loglamaslik/qaytarmaslik shart (TZ 18).

Boshlashdan oldin: `CompanionDirector.cpp`, `CompanionBridgePoller.cpp/.h`,
`CompanionLipSync.h`, `Config/DefaultEngine.ini` va `Docs/UNREAL_SETUP.md`ni o'qib chiq,
keyin 1-bosqichdan (Director'ni kafolatlash) boshla.
