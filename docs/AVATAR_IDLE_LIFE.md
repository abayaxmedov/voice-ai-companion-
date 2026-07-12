# Avatar "tiriklik" — idle animatsiya (ko'z, bosh, mimika, nafas)

Personaj gapirmaganda ham tirik ko'rinishi uchun qo'shilgan protsessual idle
tizim. Hammasi **C++da, to'liq avtomatik** — hech qanday qo'lda Blueprint/GUI
qadam yo'q. Barchasi mavjud LiveLink yuz kanali (`LLink_Face_Subj`) orqali
uzatiladi, ya'ni lab-sinxron bilan bir xil, tasdiqlangan yo'l.

## Nima qo'shildi

| Xususiyat | Qayerda | Mexanizm |
|---|---|---|
| Ko'z nigohi (saccade + drift) | `CompanionLipSync::ApplyIdleGaze` | ARKit `eyeLookIn/Out/Up/Down` curve'lari; tasodifiy sakrash (0.8–3s), drift, 30% kameraga qarash |
| Bosh harakati | `CompanionLipSync::ApplyIdleHead` | `HeadYaw/HeadPitch/HeadRoll` xossalari yuz subjectiga qo'shiladi; ABP `BasicRole` bilan o'qib bosh suyagini buradi |
| Mikro-mimika | `CompanionLipSync::ApplyMicroExpression` | sekin `browInnerUp/mouthSmile/cheekSquint` Perlin drift (~0.05) |
| Pirpirash (tabiiy) | `CompanionLipSync::ApplyAutoBlink` | qo'sh pirpirash (22%), gapirganda tez-tez, holatga bog'liq |
| Nafas | `ApplyIdleHead` ichida | sekin (~4.2s) bosh pitch tebranishi (HeadTranslation ABP'da yo'q) |
| Holat ansambli | gaze/head/blink + mood | listening/thinking/speaking uchun nigoh+bosh+pirpirash muvofiqlashadi |

## Muhim o'lchov topilmalari

Bularning barchasi headless `-game` rejimida raqam bilan tasdiqlangan
(ko'rinishga tayanilmagan):

1. **Bosh masshtabi = ~14x.** ABP `HeadYaw/Pitch/Roll` birligini ~14° bosh
   burilishiga aylantiradi (o'lchandi: `HeadYaw=10` → bosh suyagi yaw ~140°).
   Shuning uchun HAQIQIY gradus qiymati `HeadDegPerUnit` (=14) ga bo'linib
   uzatiladi. Aks holda ~35° "flop" bo'lardi.
2. **HeadTranslation ABP'da YO'Q.** `HeadTranslationZ=1.0` bosh joylashuvini
   o'zgartirmadi (154.7→154.6, faqat shovqin). Shuning uchun nafas bosh pitch
   bilan taqlid qilinadi (portret kadr uchun yetarli).
3. **Bosh alohida subject emas.** `LLink_Face_Head` — bu bool gate (subject
   emas); bosh o'sha yuz subjectidan HeadYaw/Pitch/Roll xossalari orqali
   o'qiladi. Director gate'larni (`LLink_Face_Head`, `HeadControlSwitch`) yoqadi.

## Sozlanadigan UPROPERTY'lar (`UCompanionLipSync`)

Vizual tuning uchun (masalan harakat ko'p/kam bo'lsa):

| Xossa | Sukut | Ma'nosi |
|---|---|---|
| `bEnableIdleGaze` | true | ko'z nigohi yoqiq |
| `GazeAmplitude` | 0.35 | nigoh og'ishi (0..1 ARKit birligi) |
| `SpeakingGazeScale` | 0.45 | gapirganda nigoh siqilishi |
| `bEnableIdleHead` | true | bosh harakati yoqiq |
| `HeadAmplitudeDeg` | 2.5 | idle bosh amplitudasi (HAQIQIY gradus) |
| `SpeakingHeadEmphasisDeg` | 3.0 | gapirganda bosh urg'usi |
| `HeadDegPerUnit` | 14.0 | ABP masshtab kalibratsiyasi (odatda tegilmaydi) |
| `bEnableMicroExpression` | true | mikro-mimika yoqiq |
| `MicroExpressionAmplitude` | 0.05 | mimika drift kuchi |
| `bEnableBreathing` | true | nafas yoqiq |
| `BreathPeriodSec` | 4.2 | nafas davri |
| `BreathPitchDeg` | 0.7 | nafas pitch amplitudasi |
| `bAutoBlink` | true | pirpirash yoqiq |

Belgi (sign) eslatmasi: bosh biaslari (thinking roll+4°, listening pitch−2.5°)
va nafas yo'nalishi ABP MakeRotator belgisiga bog'liq. Vizual tekshiruvda
teskari ko'rinsa — tegishli qiymat belgisini teskari qiling yoki
`HeadDegPerUnit` belgisini almashtiring.

## Tekshirish (headless, o'lchanadigan)

```bash
# Idle tiriklik (bridge/stack SHART EMAS — idle BeginPlay'dan boshlanadi):
python3 unreal/CompanionAvatar/Tools/verify_idle_life.py
# PASS misoli: nigoh=0.34 saccades=7 bosh=1.67° suyak=8.25° nafas=0.00..1.00
```

Runtime'da `CompanionDirector` avtomatik logga yozadi:
`Idle tiriklik OK (nigoh max=.., saccades=.., bosh gradus=.., bosh suyagi
og'ishi=.. deg, nafas=..)`. Agar `bosh gradusi bor-u suyak qimirlamasa` —
gate/subject uzilgan (ogohlantirish chiqadi).

## Ekspressiv idle v2 (2026-07-12, Unclaw tahlilidan keyin)

Unclaw bilan eng katta farqni yopadi ("breathes between words"):

| Xususiyat | Qayerda | Mexanizm |
|---|---|---|
| Ifoda tsikllari | `ApplyIdleExpression` | yuz 4 iliq holat orasida sekin blend (neutral_warm/soft_smile/open_smile/gentle_curious), har 5–13s, gapirganda pasayadi |
| Katta imo-ishoralar | `UpdateGesture` + `ApplyIdleHead` | har 18–55s bosh ~15° chetga burilib qaytadi (envelope: kirish/ushlash/chiqish); GestureMaxDeg=20° cap |
| Hodisa-reaksiyasi | `TriggerReaction` (Director'dan) | avatar.state listening/thinking'da "e'tibor" burilishi (xabar kelganda jonlanish) |

Sozlanadigan UPROPERTY'lar (v2): `ExpressionHoldMin/MaxSec`, `ExpressionAmplitude`,
`GestureIntervalMin/MaxSec`, `GestureYawDeg` (~15°), `GestureDurationSec`,
`GestureMaxDeg`. Barchasi `bEnable*` bilan o'chirsa bo'ladi.

Validator (`verify_idle_life.py`) endi ifoda tsikli sonini va imo-ishora
ta'sirini ham tekshiradi. PASS misoli: `ifoda_tsikllari=3 imo-ishora=1(5.2deg)`.

## Sahna v2 — Unclaw yoritish rigi (`Tools/build_stage.py`)

Kinematik portret yoritish (headless idempotent):
- **Key:** iliq oq, old-chapdan tepadan (yuzni ochadi).
- **Rim1 (accent):** QIZIL, orqa-yuqori-o'ngdan, 90cd — soch silueti + kadr
  yuqori-o'ng yog'dusi (Unclaw imzosi).
- **Rim2:** qizil, orqa-chapdan, 40cd — yumshoq wrap.
- **Fill:** sovuq ko'k, oldindan, 16cd.
- **PostProcess:** vignette 0.5 + bloom 0.7 + iliq/qizg'ish ambient.
- **Parametrlar:** `ACCENT_COLOR` (Unclaw'da 7 preset — bizda bitta qatorni
  o'zgartiring), `LIGHT_RIG_YAW` (butun rigni aylantirish — Unclaw dial).

## Cheklovlar / qo'lda qoladigan qadam

- **Personaj dizayni (mesh/teri/soch/kiyim) — MetaHuman Creator (GUI):** sepkil,
  messy bun soch, kiyim — bularni headless yaratib bo'lmaydi. Unclaw'ning
  "realizm-through-imperfection" tamoyili bilan MetaHuman Creator'da alohida
  sessiya kerak (`UNCLAW_REFERENCE.md` 3-bo'lim, `TODO.md` 11-band).
- **Ko'krak/yelka nafasi yo'q.** Portret uchun bosh nafasi bilan taqlid;
  to'liq ko'krak nafasi Body ABP tahririni talab qiladi (doiradan tashqari).
- Harakat/yoritish amplitudalari o'lchab xavfsiz oraliqqa qo'yilgan; yakuniy
  "his" vizual tekshiruvda (`scripts/dev/run_full_stack.sh`) sozlanadi.
