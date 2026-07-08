# Yuz lab-sinxroni — endi TO'LIQ AVTOMATIK (LiveLink orqali)

> **2026-07-08 yangilanish.** Oldingi qo'llanma Face AnimBP'ga qo'lda
> "Modify Curve" qo'shishni o'rgatardi. Tekshiruv shuni ko'rsatdiki, UE 5.8
> ichki Creator'da yig'ilgan bu MetaHuman'da **tahrirlanadigan Face_AnimBP
> umuman yo'q** (yuz rigi post-process ABP ichida) — ya'ni o'sha yo'l ishlamasdi.
> Buning o'rniga MetaHuman'ning **tayyor ARKit/LiveLink yo'li** ishlatildi va
> hammasi C++da avtomatlashtirildi. **Endi hech qanday qo'lda GUI qadam yo'q.**

## Qanday ishlaydi

```text
UCompanionLipSync (har tick ARKit curve'lar: jawOpen, mouthSmileLeft, ...)
        │  LiveLink push ("LLink_Face_Subj" subject, CamelCase+lowercase nomlar)
        ▼
ABP_MH_LiveLink (MetaHuman bilan birga keladi: LiveLink Pose tuguni)
        │  PA_MetaHuman_ARKit_Mapping (ARKit → yuz rigi pozalari)
        ▼
Face mesh post-process rigi → lablar/qoshlar harakati
```

Buni CompanionDirector o'zi o'rnatadi (BeginPlay'da):
1. MetaHuman aktyoriga `CompanionLipSync` komponentini qo'shadi — u LiveLink
   subject'ini ro'yxatga oladi va har tick curve qiymatlarini push qiladi
   (avto-pirpirash bilan);
2. BP'dagi `UseARKit`/`UseLiveLink` bayroqlarini yoqadi, BP'ning o'z
   `LiveLinkSetup` funksiyasini chaqiradi va kafolat uchun Face mesh anim
   klassini `ABP_MH_LiveLink`ga o'tkazadi.

## Ishlayotganini qanday bilish mumkin

**Runtime tekshiruv (avtomatik):** gapirish boshlangach ~1.5 soniyada UE
logida shulardan biri chiqadi:

```text
CompanionDirector: Yuz curve oqimi OK (jawOpen lipsync=0.42, anim=0.40)   ← ULANGAN
CompanionDirector: Yuz rigi curve O'QIMAYAPTI (...)                        ← muammo
```

**Editor'da ko'z bilan:** Window → Virtual Production → Live Link —
ro'yxatda yashil "LLink_Face_Subj" subject ko'rinishi kerak (PIE paytida).

**Statik tekshiruv (editor'siz, tez):**

```bash
python3 unreal/CompanionAvatar/Tools/verify_face_curves.py
```

## Muammolar

| Belgisi | Sabab / yechim |
|---|---|
| Logda "LiveLink mavjud emas" | LiveLink plugini o'chiq — .uproject'da yoqilgan, editor restart qiling |
| "Yuz rigi curve O'QIMAYAPTI" | Log'da "ABP_MH_LiveLink yuklanmadi" bormi? Content/MetaHumans/Common/Animation mavjudligini tekshiring |
| Lablar juda kech qimirlaydi | Bridge poll kechikishi (~0.25s) — normal; audio-sync kanali alohida vazifada |
| Ko'z pirpirashi yo'q | LipSync `bAutoBlink=true` (sukut) — Director log'ida LipSync ulanganini tekshiring |
| Subject o'zgaruvchisi buzilgan (masalan editor tajribasidan qolgan qiymat) | Muammo emas — Director runtime'da har doim `LLink_Face_Subj`ga majburan to'g'irlaydi (2026-07-08 jonli testda aynan shu holat topilib tuzatilgan) |

**Jonli tasdiqlangan (2026-07-08, mock provayderlar, headless -game):**
`Yuz curve oqimi OK (jawOpen lipsync=0.47, anim=0.28)` — LipSync qiymati
MetaHuman yuz rigigacha yetib borgani o'lchab tasdiqlandi.

## Qo'lda muqobil (agar kerak bo'lsa)

C++ avtomatikasi o'chirilsa ham (masalan `bPushLiveLink=false`), xuddi shu
zanjirni qo'lda yoqish mumkin: level'dagi BP_NewMetaHumanCharacter'ni tanlab,
Details panelida **Use ARKit** katagini belgilang — subject nomi sukut bo'yicha
`LLink_Face_Subj`. Boshqa hech narsa kerak emas.
