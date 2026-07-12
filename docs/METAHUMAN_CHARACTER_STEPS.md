# Personaj dizayni — MetaHuman Creator sessiyasi (qolgan yagona GUI ish)

> Bu loyihaning **yagona** qolgan qo'lda qadamidir. Qolgan hamma narsa
> (sahna, yoritish, jonlilik, lab-sinxron, streaming) C++/skript bilan tayyor.
> Personajning tashqi ko'rinishi (mesh/teri/soch/kiyim) esa MetaHuman Creator —
> GUI vositasida yaratiladi, uni headless qilib bo'lmaydi.
>
> Xohlasangiz men buni **teach mode** bilan qadam-baqadam ko'rsataman (ekranda
> tooltip'lar bilan) — shunchaki "MetaHuman'ni birga qilaylik" deng.

## Maqsad: "realizm nomukammallik orqali"

Unclaw avatari **ideal emas** — aynan shuning uchun tirik ko'rinadi
(`UNCLAW_REFERENCE.md` 3-bo'lim). Bizniki 1:1 nusxa BO'LMASLIGI kerak (o'z
qahramonimiz), lekin realizm darajasi shu bo'lsin. Tamoyil: **"girl next door",
studiya reklama emas.**

## Qadamlar (UE 5.8 ichki MetaHuman Creator)

1. **UE'ni oching** (`CompanionAvatar.uproject`) → Window → **MetaHuman Creator**
   (yoki Content/MetaHumans ichidagi mavjud `NewMetaHumanCharacter`ni tahrirlang).
2. **Yuz — teri detali (eng muhim):**
   - Teri toni: och-o'rtacha, iliq (neutral emas — bir oz issiq).
   - **Sepkil/freckles: KUCHLI** — burun va yonoqlar bo'ylab. Bu eng katta
     "realizm" signali.
   - Mayda nomukammalliklar: bir-ikki xol/dog', teri teksturasi (pore) o'rtacha
     kuchli. Silliq "plastik" teridan qoching.
   - Peshona/burun uchida yengil yaltirash (specular) — quruq mat emas.
3. **Ko'zlar:** to'q jigar (yoki tabiiy); qovoqlar biroz "yashagan" ko'rinishda;
   qosh o'rtacha qalin, tabiiy (juda ideal shakl bermang).
4. **Og'iz/tishlar:** lablar tabiiy teksturali; **tishlar oqartirilmagan**
   (biroz nomukammal, real). Default ifoda — yengil iliq tabassum.
5. **Soch (Groom emas, CARDS — 8GB Mac uchun muhim):**
   - Uslub: **yuqorida bo'sh/tartibsiz tugun (messy bun)** + **qoshgacha kokil
     (bangs)** + yonlarda yuzni hoshiyalovchi tolalar. Chiqib turgan, uchgan
     tolalar bo'lsin (juda tartibli emas).
   - Rang: to'q jigar-qora.
   - **Hair: Cards** (Grooms og'ir — 8GB Mac'da sekinlashtiradi).
6. **Tana/kiyim:** oddiy, zamonaviy — masalan yumshoq jemper/hoodie + oddiy shim.
   Yorqin, sof rang (bizning sahnada ko'k yaxshi ishlaydi, qizil rim bilan
   kontrast). MetaHuman default kiyimlaridan tanlang.
7. **Import sozlamalari (M-chip):** Export quality **Optimized** (Cinematic
   emas), LOD 0–2, Hair **Cards**, LOD Sync 1.

## Muhim: nomni SAQLANG

- Yangi personajni yaratsangiz, Blueprint nomida **"MetaHuman"** so'zi bo'lsin
  (masalan `BP_CompanionCharacter` YOMON; `BP_MetaHumanCompanion` YAXSHI) —
  `CompanionDirector` aktyorni nomida "MetaHuman" bor deb qidiradi
  (`MetaHumanActorNameContains`, o'zgartirsa ham bo'ladi).
- Face mesh nomida **"Face"** bo'lsin (standart MetaHuman shunday) — lab-sinxron
  shu mesh'ni topadi.
- ARKit/LiveLink yuz rigi (`ABP_MH_LiveLink`) standart MetaHuman bilan keladi —
  Director uni avtomatik ulaydi, siz tegmang.

## Tekshirish

Personajni yangilagach:
```bash
# Sahna hali kafolatlangan (yangi personaj (0,0,0) da, kameraga qaragan):
UnrealEditor-Cmd ... -run=pythonscript -script=.../Tools/build_stage.py ...
# Lab-sinxron + idle hali ishlayotganini tasdiqlang:
python3 unreal/CompanionAvatar/Tools/verify_idle_life.py    # PASS bo'lishi kerak
python3 unreal/CompanionAvatar/Tools/verify_face_curves.py  # zanjir butun
```

Agar `verify_face_curves.py` "ULANMAGAN" desa — yangi personajda ARKit yuz rigi
boshqacha ulangan bo'lishi mumkin; `docs/FACE_ANIMBP_STEPS.md`ga qarang.
