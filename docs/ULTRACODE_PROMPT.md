# Ultracode (Fable 5) uchun prompt — UE kodini tekshirish + qolganini tugatish

> Buni Code bo'limidagi Ultracode'ga to'liq nusxalab bering.

---

Sen `/Users/user/projects/ai_model` repozitoriysida ishlaysan (Ultracode, fayl +
terminal + build imkoniyati bilan). Bu "Ovozli Hamroh" — o'zbek tilida faqat ovozli
AI hamroh. Python backend, Electron/web frontend, Three.js avatar **tayyor va ishlaydi**.
Sen faqat **Unreal Engine MetaHuman + Pixel Streaming** qismini oxiriga yetkazasan.

## Vazifang (uch qism)

1. **Mening oxirgi kodimni va butun UE C++/config'ni tekshir** (review + verify):
   modul haqiqatan build bo'lsin, testlar o'tsin, xatolarni top va tuzat.
2. **Qolgan sahna + 3D character ishini imkon qadar avtomatlashtirib tugat** —
   ayniqsa qo'lda qolgan yagona GUI qadam (Face AnimBP lab-sinxron) ni UE Python
   editor scripting (headless `UnrealEditor-Cmd` / commandlet) bilan avtomatlashtirishga
   HARAKAT qil; iloji bo'lmasa — mustahkam, tekshirilgan qo'llanma + validatsiya
   skripti qoldir.
3. **Uchidan-uchigacha (end-to-end) tekshir** (mock provayderlar bilan, kalitsiz) va
   ishni commit qil.

## Hozirgi holat (aniq)

- Branch: `feat/unreal-metahuman-cpp-autowire`. **Commit qilinmagan o'zgarish bor:**
  `unreal/CompanionAvatar/Source/CompanionAvatar/CompanionLipSync.h` — men har ARKit
  curve uchun `BlueprintPure` getter qo'shdim (`GetJawOpen`, `GetMouthClose`,
  `GetMouthFunnel`, `GetMouthPucker`, `GetMouthSmileLeft/Right`,
  `GetMouthStretchLeft/Right`, `GetBrowInnerUp`) — Face AnimBP'da Property Access
  bilan bir bosishda ulash uchun. **Birinchi ishing: shu getterlarni tekshir**
  (nomlar `GetCurveValue`dagi ARKit nomlariga mos, inline, build buzmasin), keyin
  boshqa ishlarni qil.
- UE C++ (`unreal/CompanionAvatar/Source/CompanionAvatar/`):
  - `CompanionGameMode` — `GlobalDefaultGameMode`; `StartPlay`da sahnada
    `ACompanionDirector` bo'lmasa spawn qiladi.
  - `CompanionDirector` — BeginPlay'da: view target → birinchi `ACineCameraActor`;
    MetaHuman aktyorini topib `UCompanionLipSync` qo'shadi; poller `OnAvatarPlayJob`
    → `LipSync.StartJob(...)` (C++ delegate). Blueprint kerak emas.
  - `CompanionBridgePoller` — :8770 bridge'ga `ready` (retry bilan), hodisa poll;
    `PlayerUrl` sukut `http://127.0.0.1:80`, `?AutoConnect=true&...&HideUI=true`.
  - `CompanionLipSync` — viseme+curve evaluatori (avatar3d.js mantiqining porti),
    ARKit `GetCurveValue(FName)` + mening yangi getterlarim.
- Config: `Config/DefaultEngine.ini` (GameDefaultMap=/Game/CompanionStage,
  GlobalDefaultGameMode=CompanionGameMode, PixelStreaming2 sozlamalari),
  `Config/DefaultGame.ini` (PS2 ConnectionURL=ws://127.0.0.1:8888, AutoStartStream).
- Level: `Content/CompanionStage` — 5 aktyor: `BP_NewMetaHumanCharacter` (0,0,0),
  `CineCameraActor` (220,0,145 / Yaw180 / 35mm), `DirectionalLight` (40 lux),
  `SkyLight`, `PointLight` (qizil rim -90,35,175 / 60cd).
- MetaHuman: `Content/MetaHumans/NewMetaHumanCharacter/` (yig'ilgan, Face DNA + Baked
  teksturalar repoda). Face AnimBP: `.../Face/` ichida.
- Skriptlar: `scripts/dev/run_pixel_streaming_signalling.sh`,
  `scripts/dev/run_unreal_stream.sh` (HEADLESS ham), `scripts/dev/run_stack.py`
  (orchestrator :8765 + bridge :8770).
- Qo'llanmalar: `unreal/CompanionAvatar/Docs/UNREAL_SETUP.md`,
  `docs/FACE_ANIMBP_STEPS.md`, `docs/UE_HANDOFF_PROMPT.md`,
  `unreal/CompanionAvatar/Docs/EVENT_CONTRACT.md`.

## Bosqichlar va qabul mezonlari

**A. Kodni tekshirish/build**
- `CompanionLipSync.h` getterlarni + butun modulni ko'zdan kechir; UE modulni
  headless build qil (UnrealBuildTool / `Build.sh`), xatolarni tuzat.
- Orchestrator testlari: `cd services/orchestrator && python3 -m unittest discover -s tests`
  (68 test o'tishi kerak). Bridge sanity + lip-sync smoke: `scripts/dev/smoke_runtime.py`.
- Qabul: modul WARN'siz build, testlar yashil.

**B. Sahna/character to'liqligini kafolatlash (Python editor scripting bilan)**
- `UnrealEditor-Cmd` + `unreal` Python API orqali (headless) tekshir/ta'minla:
  `CompanionStage`da 5 aktyor bor; yoritish/kamera qiymatlari to'g'ri; agar biror
  narsa yo'q bo'lsa — Python skript bilan qayta yarat (idempotent
  `Tools/build_stage.py` yozib qo'y — kelajakda sahnani noldan tiklaydi).
- Qabul: skript ishga tushsa, CompanionStage kafolatlangan holatga keladi.

**C. Face AnimBP lab-sinxron — avtomatlashtirishga urin**
- UE Python (`unreal.AnimGraph`/`AnimBlueprint` API) bilan Face AnimBP'ga Modify Curve
  tuguni qo'shib, 9 curve'ni (jawOpen, mouthClose, mouthFunnel, mouthPucker,
  mouthSmileLeft/Right, mouthStretchLeft/Right, browInnerUp) `LipSync` getterlariga
  bog'lashga HARAKAT qil (`Tools/wire_face_animbp.py`).
- Agar AnimGraph'ni Python bilan ishonchli tahrirlab bo'lmasa (ehtimol) — buni ochiq
  yoz, `docs/FACE_ANIMBP_STEPS.md`ni yangilab, aniq qo'llanma + tekshiruvchi skript
  (`Tools/verify_face_curves.py` — runtime'da curve qiymatlari yozilyaptimi) qoldir.
- Qabul: yo avtomatik ulanadi, yo qat'iy qo'llanma + validator tayyor.

**D. Pixel Streaming end-to-end (mock, kalitsiz)**
- Skriptlarni tekshir/tuzat: signalling (80+8888), `run_stack.py`, `run_unreal_stream.sh`.
- Iloji bo'lsa headless `-game` + PS2 stream ko'tar, `curl 127.0.0.1:8770/avatar/status`
  va bridge'da `avatar.play` kelishini tasdiqla. Electron `updateAvatarStream` allaqachon
  `player_url`ga o'tadi — faqat bridge ready oqimini tekshir.
- Qabul: bitta buyruq bilan butun stack ko'tariladi; matn yuborilganda bridge
  `avatar.play` oladi; stream player_url bridge'ga yetadi.

**E. Yakun**
- Hammasini commit qil (mening getter o'zgarishim ham), qisqa CHANGELOG/xulosa yoz,
  qolgan har qanday qo'lda qadamni `docs/`da aniq ro'yxatla.

## Qoidalar / cheklovlar
- UE editor GUI'sini boshqara olmaysan — lekin **headless `UnrealEditor-Cmd`,
  commandlet va `unreal` Python API** bilan editor avtomatikasini bajarishing MUMKIN.
  Blueprint qo'l ishini shuning bilan almashtirishga harakat qil.
- Har da'voni **build/test bilan tasdiqla** — "ishlaydi" deb faqat aytma.
- Foydalanuvchi Mac'i ~8GB RAM: build/PIE og'ir va sekin (2–4 daqiqa+). Og'ir
  qadamlarni ogohlantir; kerak bo'lsa `HEADLESS=1`.
- UE 5.8 (Mac) / 5.7 (Windows); Target'lar `BuildSettingsVersion.Latest`.
  Asset yangi versiyada saqlansa eskida ochilmaydi — versiyani buzma.
- Kalitlar `.env`da (git'siz): loglama/qaytarma (TZ 18).
- Three.js avatar (kundalik yechim) ishlaydi — uni buzma; UE — yakuniy sayqal.

Boshlashdan oldin: `git log --oneline -8`, `git status`, so'ng
`CompanionLipSync.h`, `CompanionDirector.cpp`, `CompanionGameMode.cpp`,
`Config/DefaultEngine.ini`, `Docs/UNREAL_SETUP.md` va `docs/FACE_ANIMBP_STEPS.md`ni
o'qib chiq. Keyin A-bosqichdan boshla.
