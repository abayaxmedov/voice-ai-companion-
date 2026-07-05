# Unreal / MetaHuman — to'liq yo'l xaritasi (macOS, Pixel Streaming → Electron)

Maqsad: Electron ilovadagi Three.js avatar o'rniga (aniqrog'i — yoniga, fallback
sifatida saqlangan holda) haqiqiy MetaHuman'ni qo'yish. UE MacBook'da lokal
ishlaydi, rendered kadr Pixel Streaming (WebRTC) orqali ilova oynasiga tushadi,
lab-sinxron/mood hodisalari mavjud bridge (8770) orqali keladi — backend
O'ZGARMAYDI.

```text
Mikrofon → Orchestrator (8765): STT → LLM → TTS(+visemes/curves)
                │
                ├─→ Electron UI (matn, holat, ovoz)
                └─→ Avatar Bridge (8770) → UE CompanionBridgePoller
                                              │  avatar.play {audio_ref, mood,
                                              │               visemes[...]}
                                              ▼
                                    MetaHuman yuz rigi (ARKit curves)
                                              │
                                    Pixel Streaming (VideoToolbox enkoder)
                                              ▼
                              Electron ichida WebRTC player (iframe)
```

Nega bu oson boshlanadi: bizning viseme/ifoda nomlarimiz ARKit standartida
(jawOpen, mouthFunnel, mouthPucker, browInnerUp...), MetaHuman yuz rigi ham
ARKit blendshape'larni tushunadi — mapping deyarli 1:1.

---

## 0-bosqich. Talablar

- **UE 5.5+** (5.6+ tavsiya — MetaHuman Creator endi editor ichida). O'rnatilgan ✅
- **Xcode (to'liq, App Store'dan)** — C++ modul kompilyatsiyasi uchun.
  Terminalda bir marta: `sudo xcodebuild -license accept` va
  `xcode-select -p` `/Applications/Xcode.app/...` ko'rsatishini tekshiring.
- Disk: UE ~30GB + MetaHuman 2-5GB + DerivedDataCache 5-10GB.
- Epic hisobi (MetaHuman yuklab olish uchun).
- Python stack ishlashi: `python3 scripts/dev/run_stack.py`
  (orchestrator 8765 + bridge 8770).

## 1-bosqich. Loyihani ochish va kompilyatsiya

1. `unreal/CompanionAvatar/CompanionAvatar.uproject` ustida ikki marta bosing.
2. "Missing modules... rebuild?" so'rasa — **Yes**. Birinchi kompilyatsiya
   5-15 daqiqa.
3. Xato bo'lsa: Finder'da .uproject → o'ng tugma → Services →
   "Generate Xcode Project" → ochilgan Xcode'da build, xato matnini o'qing
   (odatda Xcode litsenziyasi yoki versiya nomuvofiqlgi).
4. Editor ochilgach: Output Log'da `CompanionAvatar` moduli yuklangani
   ko'rinsin.

## 2-bosqich. Pluginlar

Edit → Plugins:
- **Pixel Streaming** (5.5+ da "Pixel Streaming 2" ham bor — ikkalasidan birini
  tanlang; yangi loyihada PS2 tavsiya) — yoqing, restart.
- MetaHuman (5.6 ichki Creator uchun) — yoqing.
- Boshqa hech narsa kerak emas: HTTP/Json modullari Build.cs'da bor.

## 3-bosqich. MetaHuman olish

**UE 5.6+:** Window → MetaHuman Creator → belgi yarating/tayyorini tanlang →
loyihaga import. **UE 5.5:** Fab (eski Quixel Bridge) orqali MetaHuman'ni
yuklab oling va import qiling.

Import sozlamalari (M-chip uchun muhim):
- Export quality: **Optimized** (Cinematic emas).
- Hair: **Cards** (Grooms og'ir; keyin xohlasangiz almashtirasiz).
- LODs: 0-2 yetadi.

## 4-bosqich. Sahna — /Game/Maps/CompanionStage

Three.js'dagi kompozitsiyani aynan ko'chiramiz (qiymatlar boshlang'ich nuqta,
ko'z bilan sozlang):

- **Kamera (CineCameraActor):** balandlik ko'z chizig'idan ~15sm past,
  masofa ~1.1m, ~3° yuqoriga qaragan; Focal Length ~50mm (fov ~25° ga mos);
  kadrda bosh yuqori uchdan birida, ko'krak ko'rinadi.
- **Key (SpotLight, iliq):** old-chapdan yuqoridan, rang (1.0, 0.86, 0.75),
  Intensity ~8 cd, Cone yumshoq (Inner 20°/Outer 40°), soya yoqilgan.
- **Fill (RectLight, sovuq):** old-o'ngdan, rang (0.31, 0.44, 0.9),
  Intensity ~2 cd, soyasiz.
- **Rim (2x SpotLight, qizil):** orqa-o'ng kuchli (1.0, 0.15, 0.2, ~15 cd),
  orqa-chap xiraroq (~7 cd) — sochlar chetida qizil chiziq.
- **Fon:** katta plane yoki Post Process'da qora-qizil radial gradient
  material (markaz #571724 → chet #060304), yengil vignette.
- Tone mapping: UE'ning standart Filmic (ACES) — hech narsa qilinmaydi.
- Idle: MetaHuman'ning standart Idle animatsiyasi + AnimBP'da yengil nafas.

## 5-bosqich. Bridge'ni ulash va tekshirish

1. Sahnadagi biror aktyorga (masalan bo'sh `BP_CompanionDirector`)
   **CompanionBridgePoller** komponentini qo'shing.
2. Blueprint'da hodisa stublari: `OnAvatarPlayEvent` → Print String;
   `OnAvatarStateEvent` → Print String.
3. Test: `python3 scripts/dev/run_stack.py` ishlayotganda Electron/webdan
   matn yuboring — UE Output Log'da `avatar.play` ko'rinishi kerak
   (bridge navbatidagi hodisalar `GET http://127.0.0.1:8770/avatar/events`
   da ham ko'rinadi).

## 6-bosqich. Audio ijro

`audio_ref` — lokal URL (`http://127.0.0.1:8765/audio/cache/xxx.wav`,
PCM 16-bit mono 24kHz WAV — atayin shunday qilingan):

- HTTP bilan yuklab oling (poller'dagi kabi `FHttpModule`),
- WAV data qismini `USoundWaveProcedural`ga quying yoki (osonrog'i)
  bepul **RuntimeAudioImporter** plaginidan foydalaning,
- Ijro tugaganda bridge'ga `avatar.completed` POST qiling
  (EVENT_CONTRACT.md dagi format).
- `avatar.interrupt` kelsa — 200 ms ichida to'xtatish (fade 100ms).

## 7-bosqich. Lab-sinxron (ARKit curves) — KOD TAYYOR ✅

C++ tomoni yozib qo'yilgan:
- `OnAvatarPlayJob` (poller) — viseme massivi + mouth_curves bilan keladi.
- **UCompanionLipSync** komponenti — viseme+curves fuziyasi, koartikulyatsiya,
  mood 300ms lerp, prosodiya→qosh; hammasi renderer bilan bir xil qiymatlarda.

Blueprint'da qilinadigan ish:
1. MetaHuman aktyoriga `CompanionLipSync` komponentini qo'shing.
2. `OnAvatarPlayJob` → `LipSync.StartJob(Visemes, MouthCurves, Mood)`;
   audio haqiqatan boshlangan kadrda `LipSync.StartPlayback()`
   (istasangiz sekundiga bir `SyncPlaybackTime(AudioComponent vaqti)`).
3. `OnAvatarInterruptEvent` → `LipSync.StopJob()`;
   `OnAvatarStateEvent` → `LipSync.SetCompanionState(State)`.
4. Face AnimBP AnimGraph'ida **Modify Curve** tugunlari:
   har ARKit curve uchun `LipSync.GetCurveValue("jawOpen")` va h.k.
   (to'liq curve ro'yxati CompanionLipSync.h izohida).
5. Bosh ta'kidlari: `GetSpeechEnergy()` → AnimBP'da boshning yengil
   pitch/roll qo'shimchasi.

## 8-bosqich. Holatlar

`avatar.state` (idle/listening/thinking/speaking/error) → AnimBP state
machine: listening'da bosh yengil egilgan, thinking'da nigoh yuqori-chapga,
speaking'da bosh ta'kidlari (7-bosqich energiyasidan).

## 9-bosqich. Pixel Streaming (lokal)

1. Signalling server: Epic'ning `PixelStreamingInfrastructure` reposini
   clone qiling → `SignallingWebServer/platform_scripts/bash/start.sh`
   (birinchi marta `setup.sh`). U 8888 (streamer) va 80/player portlarini
   ochadi — bizda 8765/8770 band, konflikt yo'q.
2. UE'da Editor Preferences → Level Editor → Play → Additional Launch
   Parameters: `-PixelStreamingURL=ws://127.0.0.1:8888`
   (PS2'da: `-PixelStreaming2SignallingURL=ws://127.0.0.1:8888`).
3. Standalone Game rejimida ishga tushiring → brauzerda
   `http://127.0.0.1/player.html` (yoki setup chiqargan player URL) —
   MetaHuman oqimi ko'rinishi kerak. macOS'da enkoder — VideoToolbox
   (avtomatik).
4. `OnAvatarReadyEvent`da poller allaqachon `player_url`ni bridge'ga yuboradi —
   PlayerUrl xossasiga haqiqiy player manzilini yozing.

## 10-bosqich. Electron'ga joylash — KOD TAYYOR ✅

app.js allaqachon `/health` dagi `avatar_bridge.stream_ready + player_url`ni
kuzatadi: UE oqimi tayyor bo'lishi bilan Three.js o'rnida WebRTC player
iframe ochiladi, oqim uzilsa avtomatik Three.js'ga qaytadi. Sizdan faqat:
poller'dagi `PlayerUrl` xossasiga haqiqiy player manzilini yozish
(9-bosqich) — qolganini `avatar.ready` hodisasi o'zi qiladi.

## M-chipda ishlash bo'yicha

- Soch: Cards; LOD Sync 1; ko'rinmas tana qismlarini yashiring.
- Lumen o'rniga: Project Settings → Global Illumination = None/SSGI,
  Reflections = SSR (bitta personajli qorong'i sahnada farq sezilmaydi).
- `t.MaxFPS 60`, kerak bo'lsa `r.ScreenPercentage 85`.
- Birinchi ochilishda shader kompilyatsiyasi uzoq — bu bir martalik.

## Qabul mezonlari (bosqichma-bosqich)

- **M1:** UE oynasida MetaHuman + yoritish/kadr Three.js versiyasiga o'xshash;
  bridge hodisalari logda ko'rinadi.
- **M2:** matn yuborilganda MetaHuman audio bilan gapiradi, lablar viseme'larga
  mos; interrupt <200ms; `avatar.completed` yuboriladi.
- **M3:** Pixel Streaming orqali Electron ichida ko'rinadi; stream uzilsa
  Three.js fallback; FPS 30+ (maqsad 60).

## Muammolar

| Belgisi | Sabab/yechim |
|---|---|
| Modul build xatosi | Xcode litsenziya (`sudo xcodebuild -license accept`), UE versiyasi .uproject bilan mos emas |
| avatar.play kelmayapti | run_stack ishlayaptimi? `curl 127.0.0.1:8770/avatar/status`; orchestrator logida "bridge unavailable" |
| Audio yo'q, `mock://` | .env'da TTS hali mock — ELEVENLABS kalitlarini kiriting |
| Stream qora ekran | Signalling server ishga tushmagan yoki launch parametri yo'q |
| Lablar qimirlamaydi | 7-bosqich kod kengaytmasi hali qilinmagan (visemes Blueprint'ga yetmayapti) |
