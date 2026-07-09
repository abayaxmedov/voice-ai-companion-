#include "CompanionLipSync.h"

#include "CompanionLiveLinkSource.h"
#include "Features/IModularFeatures.h"
#include "ILiveLinkClient.h"
#include "LiveLinkTypes.h"
#include "Roles/LiveLinkAnimationRole.h"
#include "Roles/LiveLinkAnimationTypes.h"

#include <initializer_list>

namespace
{
    using FShape = TArray<TPair<FName, float>>;

    FShape MakeShape(std::initializer_list<TPair<FName, float>> Pairs)
    {
        FShape Shape;
        Shape.Reserve(static_cast<int32>(Pairs.size()));
        for (const TPair<FName, float>& Pair : Pairs)
        {
            Shape.Add(Pair);
        }
        return Shape;
    }

    float Smoothstep(float X)
    {
        X = FMath::Clamp(X, 0.f, 1.f);
        return X * X * (3.f - 2.f * X);
    }
}

UCompanionLipSync::UCompanionLipSync()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UCompanionLipSync::BeginPlay()
{
    Super::BeginPlay();
    ResetCurves();
    // Har instansiya uchun boshqacha noise fazasi — mexanik takror bo'lmasin.
    NoiseSeed = FMath::FRandRange(0.f, 1000.f);
    GazeTimer = FMath::FRandRange(0.4f, 1.6f);
    if (bPushLiveLink)
    {
        SetupLiveLink();
    }
}

void UCompanionLipSync::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    TeardownLiveLink();
    Super::EndPlay(EndPlayReason);
}

namespace
{
    // Evaluator hisoblaydigan barcha ARKit curve'lar + avto-pirpirash.
    const TCHAR* GCompanionArkitCurves[] = {
        TEXT("jawOpen"), TEXT("jawForward"), TEXT("mouthClose"),
        TEXT("mouthFunnel"), TEXT("mouthPucker"),
        TEXT("mouthSmileLeft"), TEXT("mouthSmileRight"),
        TEXT("mouthStretchLeft"), TEXT("mouthStretchRight"),
        TEXT("mouthPressLeft"), TEXT("mouthPressRight"),
        TEXT("mouthShrugUpper"), TEXT("mouthShrugLower"),
        TEXT("mouthLowerDownLeft"), TEXT("mouthLowerDownRight"),
        TEXT("mouthUpperUpLeft"), TEXT("mouthUpperUpRight"),
        TEXT("mouthDimpleLeft"), TEXT("mouthDimpleRight"),
        TEXT("mouthFrownLeft"), TEXT("mouthFrownRight"),
        TEXT("mouthRollUpper"), TEXT("mouthRollLower"), TEXT("mouthLeft"),
        TEXT("browInnerUp"), TEXT("browDownLeft"), TEXT("browDownRight"),
        TEXT("browOuterUpLeft"), TEXT("browOuterUpRight"),
        TEXT("eyeSquintLeft"), TEXT("eyeSquintRight"),
        TEXT("eyeWideLeft"), TEXT("eyeWideRight"),
        TEXT("cheekSquintLeft"), TEXT("cheekSquintRight"),
        TEXT("eyeBlinkLeft"), TEXT("eyeBlinkRight"),
        // Ko'z nigohi (idle saccade + drift).
        TEXT("eyeLookInLeft"), TEXT("eyeLookInRight"),
        TEXT("eyeLookOutLeft"), TEXT("eyeLookOutRight"),
        TEXT("eyeLookUpLeft"), TEXT("eyeLookUpRight"),
        TEXT("eyeLookDownLeft"), TEXT("eyeLookDownRight"),
    };

    // Bosh rotatsiyasi (gradus) — clamp'siz, alohida yo'l bilan uzatiladi.
    // (HeadTranslation'ni ABP qo'llab-quvvatlamasligi o'lchab tasdiqlandi —
    //  nafas shuning uchun bosh pitch tebranishi bilan taqlid qilinadi.)
    const TCHAR* GCompanionHeadProps[] = {
        TEXT("HeadYaw"), TEXT("HeadPitch"), TEXT("HeadRoll"),
    };
}

void UCompanionLipSync::SetupLiveLink()
{
    if (!IModularFeatures::Get().IsModularFeatureAvailable(ILiveLinkClient::ModularFeatureName))
    {
        UE_LOG(LogTemp, Warning,
            TEXT("CompanionLipSync: LiveLink mavjud emas (plugin o'chiqmi?) — yuz curve'lari push qilinmaydi"));
        return;
    }

    LiveLinkClient = &IModularFeatures::Get().GetModularFeature<ILiveLinkClient>(ILiveLinkClient::ModularFeatureName);
    LiveLinkSource = MakeShared<FCompanionLiveLinkSource>();
    LiveLinkClient->AddSource(LiveLinkSource);

    // FName taqqoslash katta-kichik harfni farqlamaydi — bizning "jawOpen"
    // PoseAsset'dagi "JawOpen" pozasiga o'z-o'zidan mos keladi, bitta to'plam
    // yetarli.
    LiveLinkPropertyNames.Reset();
    for (const TCHAR* Curve : GCompanionArkitCurves)
    {
        LiveLinkPropertyNames.Add(FName(Curve));
    }
    // Bosh xossalari ro'yxat oxirida — ABP ularni BasicRole bilan o'qiydi
    // (yuz curve'lari uchun esa Animation role). Qiymatlari gradusda.
    for (const TCHAR* Head : GCompanionHeadProps)
    {
        LiveLinkPropertyNames.Add(FName(Head));
    }

    // MetaHuman'ning AnimNode_LiveLinkPose tuguni Animation rolini kutadi
    // (LiveLink Face ilovasi bilan bir xil): suyaklarsiz, faqat curve'lar.
    FLiveLinkStaticDataStruct StaticData(FLiveLinkSkeletonStaticData::StaticStruct());
    StaticData.Cast<FLiveLinkSkeletonStaticData>()->PropertyNames = LiveLinkPropertyNames;
    const FLiveLinkSubjectKey SubjectKey(LiveLinkSource->GetSourceGuid(), LiveLinkSubjectName);
    LiveLinkClient->PushSubjectStaticData_AnyThread(
        SubjectKey, ULiveLinkAnimationRole::StaticClass(), MoveTemp(StaticData));

    UE_LOG(LogTemp, Log, TEXT("CompanionLipSync: LiveLink subject '%s' ro'yxatga olindi (%d xossa)"),
        *LiveLinkSubjectName.ToString(), LiveLinkPropertyNames.Num());
}

void UCompanionLipSync::TeardownLiveLink()
{
    if (LiveLinkClient && LiveLinkSource.IsValid()
        && IModularFeatures::Get().IsModularFeatureAvailable(ILiveLinkClient::ModularFeatureName))
    {
        LiveLinkClient->RemoveSource(LiveLinkSource);
    }
    LiveLinkSource.Reset();
    LiveLinkClient = nullptr;
}

void UCompanionLipSync::PushLiveLinkFrame()
{
    if (!LiveLinkClient || !LiveLinkSource.IsValid())
    {
        return;
    }
    // Modul yopilgan bo'lsa keshdagi ko'rsatkich o'lik — har push oldidan arzon tekshiruv.
    if (!IModularFeatures::Get().IsModularFeatureAvailable(ILiveLinkClient::ModularFeatureName))
    {
        LiveLinkClient = nullptr;
        return;
    }

    FLiveLinkFrameDataStruct Frame(FLiveLinkAnimationFrameData::StaticStruct());
    FLiveLinkAnimationFrameData* Data = Frame.Cast<FLiveLinkAnimationFrameData>();
    Data->WorldTime = FLiveLinkWorldTime();
    Data->PropertyValues.Reserve(LiveLinkPropertyNames.Num());
    for (const FName& Source : LiveLinkPropertyNames)
    {
        // Bosh: HeadYawDeg... haqiqiy gradusda; ABP ~HeadDegPerUnit barobar
        // kuchaytiradi (o'lchangan: 1 birlik ≈ 14°), shuning uchun bo'lib beramiz.
        // Bu qiymatlar [0,1] clamp'ga tushmaydi.
        const float Scale = FMath::Max(0.01f, HeadDegPerUnit);
        if (Source == TEXT("HeadYaw")) { Data->PropertyValues.Add(HeadYawDeg / Scale); }
        else if (Source == TEXT("HeadPitch")) { Data->PropertyValues.Add(HeadPitchDeg / Scale); }
        else if (Source == TEXT("HeadRoll")) { Data->PropertyValues.Add(HeadRollDeg / Scale); }
        else { Data->PropertyValues.Add(GetCurveValue(Source)); }
    }

    const FLiveLinkSubjectKey SubjectKey(LiveLinkSource->GetSourceGuid(), LiveLinkSubjectName);
    LiveLinkClient->PushSubjectFrameData_AnyThread(SubjectKey, MoveTemp(Frame));
}

void UCompanionLipSync::ApplyAutoBlink(float DeltaTime)
{
    if (!bAutoBlink)
    {
        return;
    }

    if (BlinkPhase < 0.f)
    {
        BlinkCooldown -= DeltaTime;
        if (BlinkCooldown <= 0.f)
        {
            BlinkPhase = 0.f;
        }
    }
    else
    {
        BlinkPhase += DeltaTime / 0.14f; // to'liq pirpirash ~140ms
        if (BlinkPhase >= 1.f)
        {
            BlinkPhase = -1.f;
            if (BlinkBurstLeft > 0)
            {
                --BlinkBurstLeft;
                BlinkCooldown = 0.09f; // qo'sh pirpirash: juda qisqa tanaffus
            }
            else
            {
                // Gapirganda odam tez-tez pirpiraydi; idle'da kamroq.
                float Base = bJobActive ? 1.6f : 2.6f;
                float Span = bJobActive ? 2.2f : 3.8f;
                // Holatga bog'liq: thinking'da uzoq tikilib kamroq pirpiraydi;
                // listening'da e'tiborli, biroz tez-tez.
                if (CompanionState == TEXT("thinking")) { Base *= 1.7f; Span *= 1.5f; }
                else if (CompanionState == TEXT("listening")) { Base *= 0.85f; }
                BlinkCooldown = FMath::FRandRange(Base, Base + Span);
                // Vaqti-vaqti bilan qo'sh pirpirash (tabiiy).
                if (FMath::FRand() < 0.22f)
                {
                    BlinkBurstLeft = 1;
                }
            }
        }
    }

    if (BlinkPhase >= 0.f)
    {
        // 0->1->0 uchburchak, silliqlangan.
        const float Blink = Smoothstep(1.f - FMath::Abs(BlinkPhase * 2.f - 1.f));
        static const FName BlinkLeft(TEXT("eyeBlinkLeft"));
        static const FName BlinkRight(TEXT("eyeBlinkRight"));
        float& Left = CurveValues.FindOrAdd(BlinkLeft);
        float& Right = CurveValues.FindOrAdd(BlinkRight);
        Left = FMath::Max(Left, Blink);
        Right = FMath::Max(Right, Blink);
    }
}

void UCompanionLipSync::ApplyIdleGaze(float DeltaTime)
{
    if (!bEnableIdleGaze)
    {
        return;
    }

    // Gapirganda odam ko'proq markazga qaraydi — diapazon siqiladi.
    const float RangeScale = bJobActive ? SpeakingGazeScale : 1.f;

    GazeTimer -= DeltaTime;
    if (GazeTimer <= 0.f)
    {
        ++SaccadeCount;
        if (FMath::FRand() < 0.3f)
        {
            GazeTarget = FVector2D::ZeroVector; // kameraga (markaz) qarash
        }
        else
        {
            GazeTarget.X = FMath::FRandRange(-1.f, 1.f);
            GazeTarget.Y = FMath::FRandRange(-0.7f, 0.7f); // vertikal kamroq
        }
        // Katta saccade ko'pincha pirpirash bilan birga keladi (tabiiy).
        if ((GazeTarget - GazeCurrent).Size() > 0.9f && BlinkPhase < 0.f && FMath::FRand() < 0.5f)
        {
            BlinkPhase = 0.f;
        }
        GazeTimer = FMath::FRandRange(0.8f, 3.0f);
    }

    // Saccade — tez ko'chish; drift esa chiqishda qo'shiladi.
    GazeCurrent += (GazeTarget - GazeCurrent) * FMath::Min(1.f, DeltaTime * 12.f);

    // Holatga bog'liq nigoh siljishi (silliq lerp — sakramasin).
    FVector2D TargetBias = FVector2D::ZeroVector;
    float StateAmp = 1.f;
    if (CompanionState == TEXT("listening"))
    {
        TargetBias = FVector2D(0.f, 0.04f); // deyarli markaz (kameraga e'tibor)
        StateAmp = 0.5f;
    }
    else if (CompanionState == TEXT("thinking"))
    {
        TargetBias = FVector2D(-0.5f, 0.6f); // yuqori-chapga (o'ylash nigohi)
        StateAmp = 0.8f;
    }
    GazeStateBias += (TargetBias - GazeStateBias) * FMath::Min(1.f, DeltaTime * 3.f);

    const float T = static_cast<float>(LifeClock);
    const float DriftX = 0.06f * FMath::PerlinNoise1D(T * 0.3f + NoiseSeed);
    const float DriftY = 0.05f * FMath::PerlinNoise1D(T * 0.27f + NoiseSeed + 11.f);
    const float GX = FMath::Clamp(GazeCurrent.X * StateAmp + GazeStateBias.X + DriftX, -1.f, 1.f)
                     * GazeAmplitude * RangeScale;
    const float GY = FMath::Clamp(GazeCurrent.Y * StateAmp + GazeStateBias.Y + DriftY, -1.f, 1.f)
                     * GazeAmplitude * RangeScale;

    // ARKit konvensiyasi: +X = personaj o'ngiga qaraydi (chap ko'z In, o'ng ko'z Out).
    const float RightAmt = FMath::Max(0.f, GX);
    const float LeftAmt = FMath::Max(0.f, -GX);
    CurveValues.FindOrAdd(FName("eyeLookOutRight")) += RightAmt;
    CurveValues.FindOrAdd(FName("eyeLookInLeft")) += RightAmt;
    CurveValues.FindOrAdd(FName("eyeLookOutLeft")) += LeftAmt;
    CurveValues.FindOrAdd(FName("eyeLookInRight")) += LeftAmt;
    const float UpAmt = FMath::Max(0.f, GY);
    const float DownAmt = FMath::Max(0.f, -GY);
    CurveValues.FindOrAdd(FName("eyeLookUpLeft")) += UpAmt;
    CurveValues.FindOrAdd(FName("eyeLookUpRight")) += UpAmt;
    CurveValues.FindOrAdd(FName("eyeLookDownLeft")) += DownAmt;
    CurveValues.FindOrAdd(FName("eyeLookDownRight")) += DownAmt;
}

void UCompanionLipSync::ApplyMicroExpression()
{
    if (!bEnableMicroExpression)
    {
        return;
    }
    // Gapirganda lab-sinxronga xalaqit qilmasligi uchun kuchi pasayadi.
    const float Gain = MicroExpressionAmplitude * (bJobActive ? 0.3f : 1.f);
    const float T = static_cast<float>(LifeClock);
    const auto N = [&](float Freq, float Seed) -> float
    {
        return FMath::PerlinNoise1D(T * Freq + NoiseSeed + Seed);
    };
    CurveValues.FindOrAdd(FName("browInnerUp")) += Gain * (0.5f + 0.5f * N(0.13f, 0.f));
    CurveValues.FindOrAdd(FName("browOuterUpLeft")) += Gain * 0.4f * FMath::Max(0.f, N(0.11f, 5.f));
    CurveValues.FindOrAdd(FName("browOuterUpRight")) += Gain * 0.4f * FMath::Max(0.f, N(0.12f, 8.f));
    CurveValues.FindOrAdd(FName("mouthSmileLeft")) += Gain * 0.6f * FMath::Max(0.f, N(0.09f, 15.f));
    CurveValues.FindOrAdd(FName("mouthSmileRight")) += Gain * 0.6f * FMath::Max(0.f, N(0.1f, 18.f));
    CurveValues.FindOrAdd(FName("cheekSquintLeft")) += Gain * 0.3f * FMath::Max(0.f, N(0.08f, 21.f));
    CurveValues.FindOrAdd(FName("cheekSquintRight")) += Gain * 0.3f * FMath::Max(0.f, N(0.085f, 24.f));
}

void UCompanionLipSync::ApplyIdleHead(float DeltaTime)
{
    if (!bEnableIdleHead)
    {
        HeadYawDeg = HeadPitchDeg = HeadRollDeg = 0.f;
        return;
    }

    const float T = static_cast<float>(LifeClock);
    // Sekin, organik sway: ikki nomutanosib sinus (ishonchli amplituda) + mayda
    // Perlin (mexanik takror bo'lmasin). Davr ~8-11s.
    const auto Osc = [&](float Freq, float Phase) -> float
    {
        return 0.62f * FMath::Sin(T * Freq + NoiseSeed + Phase)
             + 0.38f * FMath::PerlinNoise1D(T * Freq * 0.25f + NoiseSeed + Phase);
    };
    float Yaw = HeadAmplitudeDeg * Osc(0.55f, 0.f);
    float Pitch = HeadAmplitudeDeg * 0.7f * Osc(0.47f, 30.f);
    float Roll = HeadAmplitudeDeg * 0.5f * Osc(0.40f, 60.f);

    // Nafas: sekin (~4-5s davr) pitch tebranishi — ko'krak ko'tarilib-tushayotgandek
    // his beradi (HeadTranslation ABP'da yo'q, shuning uchun bosh bilan taqlid).
    if (bEnableBreathing)
    {
        BreathPhase += DeltaTime / FMath::Max(1.f, BreathPeriodSec);
        BreathPhase = FMath::Fmod(BreathPhase, 1.f);
        BreathLevel = 0.5f - 0.5f * FMath::Cos(BreathPhase * 2.f * PI); // 0..1 silliq
        Pitch += BreathPitchDeg * (BreathLevel - 0.5f) * 2.f;           // ±BreathPitchDeg
    }

    if (bJobActive)
    {
        // Nutq energiyasi/pitch'iga bog'liq yengil urg'u (bosh chayqash/silkinish).
        const float E = SmoothedEnergy;
        const float PitchAccent = FMath::Max(0.f, LastPitch - 0.5f);
        Pitch += -SpeakingHeadEmphasisDeg * E * 0.6f; // gapirganda bosh biroz oldinga
        Yaw += SpeakingHeadEmphasisDeg * 0.4f * E * FMath::PerlinNoise1D(T * 0.9f + NoiseSeed);
        Roll += SpeakingHeadEmphasisDeg * 0.3f * PitchAccent;
    }

    // Holatga bog'liq bias (belgi vizual tekshiruvda sozlanishi mumkin — 2.6).
    if (CompanionState == TEXT("thinking"))
    {
        Roll += 4.0f;
        Pitch += 2.0f;
    }
    else if (CompanionState == TEXT("listening"))
    {
        Pitch -= 2.5f;
    }

    // Silliqlash — sakramasin (signal allaqachon silliq, kam lag yetadi).
    // Bu yerda HeadYawDeg/... HAQIQIY gradus (push'da HeadDegPerUnit'ga bo'linadi).
    const float S = FMath::Min(1.f, DeltaTime * 7.f);
    HeadYawDeg += (Yaw - HeadYawDeg) * S;
    HeadPitchDeg += (Pitch - HeadPitchDeg) * S;
    HeadRollDeg += (Roll - HeadRollDeg) * S;
}

// avatar3d.js VISEME_SHAPES bilan bir xil qiymatlar (ARKit nomlari).
const TMap<FString, FShape>& UCompanionLipSync::VisemeShapes()
{
    static const TMap<FString, FShape> Shapes = []()
    {
        TMap<FString, FShape> Map;
        Map.Add(TEXT("sil"), {});
        Map.Add(TEXT("PP"), MakeShape({
            {FName("mouthClose"), 0.85f}, {FName("mouthPressLeft"), 0.55f},
            {FName("mouthPressRight"), 0.55f}, {FName("jawOpen"), 0.05f},
            {FName("mouthRollLower"), 0.25f}, {FName("mouthRollUpper"), 0.2f}}));
        Map.Add(TEXT("FF"), MakeShape({
            {FName("mouthPressLeft"), 0.35f}, {FName("mouthPressRight"), 0.35f},
            {FName("jawOpen"), 0.09f}, {FName("mouthShrugUpper"), 0.2f},
            {FName("mouthRollLower"), 0.45f}, {FName("mouthLowerDownLeft"), 0.12f},
            {FName("mouthLowerDownRight"), 0.12f}}));
        Map.Add(TEXT("DD"), MakeShape({
            {FName("jawOpen"), 0.18f}, {FName("mouthShrugUpper"), 0.25f},
            {FName("mouthStretchLeft"), 0.1f}, {FName("mouthStretchRight"), 0.1f},
            {FName("mouthPressLeft"), 0.12f}, {FName("mouthPressRight"), 0.12f}}));
        Map.Add(TEXT("kk"), MakeShape({
            {FName("jawOpen"), 0.22f}, {FName("mouthShrugUpper"), 0.1f},
            {FName("mouthStretchLeft"), 0.06f}, {FName("mouthStretchRight"), 0.06f}}));
        Map.Add(TEXT("CH"), MakeShape({
            {FName("jawOpen"), 0.16f}, {FName("mouthFunnel"), 0.45f},
            {FName("mouthPucker"), 0.28f}, {FName("mouthShrugUpper"), 0.2f}}));
        Map.Add(TEXT("SS"), MakeShape({
            {FName("jawOpen"), 0.1f}, {FName("mouthSmileLeft"), 0.2f},
            {FName("mouthSmileRight"), 0.2f}, {FName("mouthStretchLeft"), 0.28f},
            {FName("mouthStretchRight"), 0.28f}, {FName("mouthShrugUpper"), 0.15f}}));
        Map.Add(TEXT("nn"), MakeShape({
            {FName("jawOpen"), 0.13f}, {FName("mouthShrugUpper"), 0.18f},
            {FName("mouthPressLeft"), 0.14f}, {FName("mouthPressRight"), 0.14f}}));
        Map.Add(TEXT("RR"), MakeShape({
            {FName("jawOpen"), 0.14f}, {FName("mouthFunnel"), 0.24f},
            {FName("mouthPucker"), 0.14f}, {FName("mouthStretchLeft"), 0.08f},
            {FName("mouthStretchRight"), 0.08f}}));
        Map.Add(TEXT("aa"), MakeShape({
            {FName("jawOpen"), 0.58f}, {FName("mouthFunnel"), 0.1f},
            {FName("mouthLowerDownLeft"), 0.22f}, {FName("mouthLowerDownRight"), 0.22f},
            {FName("mouthUpperUpLeft"), 0.16f}, {FName("mouthUpperUpRight"), 0.16f}}));
        Map.Add(TEXT("E"), MakeShape({
            {FName("jawOpen"), 0.3f}, {FName("mouthSmileLeft"), 0.22f},
            {FName("mouthSmileRight"), 0.22f}, {FName("mouthStretchLeft"), 0.18f},
            {FName("mouthStretchRight"), 0.18f}, {FName("mouthLowerDownLeft"), 0.1f},
            {FName("mouthLowerDownRight"), 0.1f}}));
        Map.Add(TEXT("I"), MakeShape({
            {FName("jawOpen"), 0.16f}, {FName("mouthSmileLeft"), 0.38f},
            {FName("mouthSmileRight"), 0.38f}, {FName("mouthStretchLeft"), 0.26f},
            {FName("mouthStretchRight"), 0.26f}}));
        Map.Add(TEXT("O"), MakeShape({
            {FName("jawOpen"), 0.42f}, {FName("mouthFunnel"), 0.55f},
            {FName("mouthPucker"), 0.34f}, {FName("mouthUpperUpLeft"), 0.08f},
            {FName("mouthUpperUpRight"), 0.08f}}));
        Map.Add(TEXT("U"), MakeShape({
            {FName("jawOpen"), 0.2f}, {FName("mouthFunnel"), 0.5f},
            {FName("mouthPucker"), 0.72f}}));
        // Eski backend formati bilan moslik.
        Map.Add(TEXT("A"), Map[TEXT("aa")]);
        Map.Add(TEXT("M"), Map[TEXT("PP")]);
        return Map;
    }();
    return Shapes;
}

// avatar3d.js MOOD_SHAPES bilan bir xil.
const TMap<FString, FShape>& UCompanionLipSync::MoodShapes()
{
    static const TMap<FString, FShape> Shapes = []()
    {
        TMap<FString, FShape> Map;
        Map.Add(TEXT("neutral"), MakeShape({
            {FName("browInnerUp"), 0.06f}, {FName("mouthSmileLeft"), 0.1f},
            {FName("mouthSmileRight"), 0.07f}, {FName("eyeSquintLeft"), 0.04f},
            {FName("eyeSquintRight"), 0.03f}}));
        Map.Add(TEXT("happy"), MakeShape({
            {FName("mouthSmileLeft"), 0.5f}, {FName("mouthSmileRight"), 0.44f},
            {FName("cheekSquintLeft"), 0.28f}, {FName("cheekSquintRight"), 0.23f},
            {FName("eyeSquintLeft"), 0.22f}, {FName("eyeSquintRight"), 0.17f},
            {FName("browInnerUp"), 0.12f}, {FName("browOuterUpLeft"), 0.08f},
            {FName("mouthDimpleLeft"), 0.24f}, {FName("mouthDimpleRight"), 0.18f}}));
        Map.Add(TEXT("excited"), MakeShape({
            {FName("mouthSmileLeft"), 0.58f}, {FName("mouthSmileRight"), 0.52f},
            {FName("browInnerUp"), 0.24f}, {FName("browOuterUpLeft"), 0.3f},
            {FName("browOuterUpRight"), 0.26f}, {FName("eyeWideLeft"), 0.24f},
            {FName("eyeWideRight"), 0.2f}, {FName("cheekSquintLeft"), 0.2f},
            {FName("cheekSquintRight"), 0.16f}, {FName("jawOpen"), 0.05f}}));
        Map.Add(TEXT("thoughtful"), MakeShape({
            {FName("browDownLeft"), 0.26f}, {FName("browDownRight"), 0.1f},
            {FName("browInnerUp"), 0.22f}, {FName("eyeSquintLeft"), 0.18f},
            {FName("eyeSquintRight"), 0.07f}, {FName("mouthPressLeft"), 0.28f},
            {FName("mouthPressRight"), 0.16f}, {FName("mouthLeft"), 0.12f}}));
        Map.Add(TEXT("concerned"), MakeShape({
            {FName("browInnerUp"), 0.5f}, {FName("browDownLeft"), 0.1f},
            {FName("browDownRight"), 0.16f}, {FName("mouthFrownLeft"), 0.26f},
            {FName("mouthFrownRight"), 0.3f}, {FName("mouthShrugLower"), 0.24f},
            {FName("eyeSquintRight"), 0.1f}}));
        Map.Add(TEXT("apologetic"), MakeShape({
            {FName("browInnerUp"), 0.44f}, {FName("mouthFrownLeft"), 0.14f},
            {FName("mouthFrownRight"), 0.17f}, {FName("mouthPressLeft"), 0.24f},
            {FName("mouthPressRight"), 0.24f}, {FName("eyeSquintLeft"), 0.12f},
            {FName("eyeSquintRight"), 0.12f}}));
        Map.Add(TEXT("reassuring"), MakeShape({
            {FName("mouthSmileLeft"), 0.3f}, {FName("mouthSmileRight"), 0.27f},
            {FName("browInnerUp"), 0.18f}, {FName("eyeSquintLeft"), 0.12f},
            {FName("mouthDimpleLeft"), 0.14f}}));
        return Map;
    }();
    return Shapes;
}

bool UCompanionLipSync::IsMouthCurve(FName CurveName)
{
    const FString Name = CurveName.ToString();
    return Name.StartsWith(TEXT("mouth")) || Name.StartsWith(TEXT("jaw")) ||
        Name.StartsWith(TEXT("cheekPuff"));
}

void UCompanionLipSync::StartJob(
    const TArray<FCompanionVisemeFrame>& Visemes,
    const FCompanionMouthCurves& MouthCurves,
    const FString& Mood)
{
    Frames = Visemes;
    Frames.Sort([](const FCompanionVisemeFrame& A, const FCompanionVisemeFrame& B)
    {
        return A.TimeMs < B.TimeMs;
    });
    Curves = MouthCurves;
    FrameIndex = 0;
    PlaybackSeconds = 0.f;
    Fade = 0.f;
    bClockRunning = false;
    bJobActive = Frames.Num() > 1 || Curves.IsUsable();
    // Timeline uzunligi — bridge'dan stop/interrupt kelmasa ham o'zimiz
    // to'xtashimiz uchun (aks holda IsSpeaking abadiy true qoladi).
    const float VisemeEnd = Frames.Num() > 0 ? Frames.Last().TimeMs / 1000.f : 0.f;
    const float CurveEnd = Curves.IsUsable()
        ? static_cast<float>(Curves.Jaw.Num()) / static_cast<float>(FMath::Max(1, Curves.Fps))
        : 0.f;
    JobDurationSeconds = FMath::Max(VisemeEnd, CurveEnd);
    SetMood(Mood);
}

void UCompanionLipSync::StartPlayback()
{
    PlaybackSeconds = 0.f;
    FrameIndex = 0;
    bClockRunning = true;
}

void UCompanionLipSync::SyncPlaybackTime(float InPlaybackSeconds)
{
    // Katta drift'nigina tuzatamiz — mayda sakrashlar ko'rinmasin.
    if (FMath::Abs(InPlaybackSeconds - PlaybackSeconds) > 0.08f)
    {
        if (InPlaybackSeconds < PlaybackSeconds)
        {
            FrameIndex = 0; // orqaga qaytish — indeksni qayta boshlaymiz
        }
        PlaybackSeconds = FMath::Max(0.f, InPlaybackSeconds);
    }
}

void UCompanionLipSync::StopJob()
{
    bJobActive = false;
    bClockRunning = false;
}

void UCompanionLipSync::SetMood(const FString& Mood)
{
    const FString Safe = MoodShapes().Contains(Mood) ? Mood : TEXT("neutral");
    if (Safe == CurrentMood)
    {
        return;
    }
    PreviousMood = CurrentMood;
    CurrentMood = Safe;
    MoodBlend = 0.f;
}

void UCompanionLipSync::SetCompanionState(const FString& State)
{
    CompanionState = State;
}

float UCompanionLipSync::GetCurveValue(FName CurveName) const
{
    if (const float* Value = CurveValues.Find(CurveName))
    {
        return *Value;
    }
    return 0.f;
}

void UCompanionLipSync::ResetCurves()
{
    for (TPair<FName, float>& Pair : CurveValues)
    {
        Pair.Value = 0.f;
    }
}

void UCompanionLipSync::AddShape(const FShape* Shape, float Multiplier, float MouthScale)
{
    if (!Shape || Multiplier <= 0.f)
    {
        return;
    }
    for (const TPair<FName, float>& Pair : *Shape)
    {
        const float Scale = IsMouthCurve(Pair.Key) ? MouthScale : 1.f;
        CurveValues.FindOrAdd(Pair.Key) += Pair.Value * Multiplier * Scale;
    }
}

void UCompanionLipSync::EvaluateMood()
{
    const float Blend = Smoothstep(MoodBlend);
    const float MouthScale = bJobActive ? SpeakingMouthMoodScale : 1.f;
    AddShape(MoodShapes().Find(PreviousMood), 1.f - Blend, MouthScale);
    AddShape(MoodShapes().Find(CurrentMood), Blend, MouthScale);
    if (CompanionState == TEXT("thinking"))
    {
        AddShape(MoodShapes().Find(TEXT("thoughtful")), 0.5f, MouthScale);
    }
}

void UCompanionLipSync::EvaluateVisemes(float TimeSeconds)
{
    const float TimeMs = TimeSeconds * 1000.f;

    // Egri chiziqlar (haqiqiy audio vaqtida).
    float CurveEnergy = -1.f, CurveJaw = 0.f, CurveClose = 0.f;
    float CurveSpread = 0.f, CurveRound = 0.f;
    if (Curves.IsUsable())
    {
        CurveEnergy = Curves.Sample(Curves.Energy, TimeSeconds);
        CurveJaw = Curves.Sample(Curves.Jaw, TimeSeconds);
        CurveClose = Curves.Sample(Curves.Close, TimeSeconds);
        CurveSpread = Curves.Sample(Curves.Spread, TimeSeconds);
        CurveRound = Curves.Sample(Curves.Round, TimeSeconds);
        LastPitch = Curves.Sample(Curves.Pitch, TimeSeconds);
    }

    const float Amp = CurveEnergy >= 0.f ? (0.55f + 0.75f * CurveEnergy) : 0.85f;

    if (Frames.Num() > 1)
    {
        while (FrameIndex + 1 < Frames.Num() &&
               static_cast<float>(Frames[FrameIndex + 1].TimeMs) <= TimeMs)
        {
            ++FrameIndex;
        }
        while (FrameIndex > 0 && static_cast<float>(Frames[FrameIndex].TimeMs) > TimeMs)
        {
            --FrameIndex;
        }
        const FCompanionVisemeFrame& Cur = Frames[FrameIndex];
        const FCompanionVisemeFrame* Next =
            FrameIndex + 1 < Frames.Num() ? &Frames[FrameIndex + 1] : nullptr;
        const float SegStart = static_cast<float>(Cur.TimeMs);
        const float SegEnd = Next ? static_cast<float>(Next->TimeMs) : SegStart + 180.f;
        const float SegLen = FMath::Max(40.f, SegEnd - SegStart);
        const float Attack = FMath::Min(60.f, SegLen * 0.5f);
        const float Release = FMath::Min(80.f, SegLen * 0.4f);
        const float WIn = Smoothstep((TimeMs - SegStart) / Attack);
        const float WOut = Next ? Smoothstep((TimeMs - (SegEnd - Release)) / Release) : 0.f;
        const float WCur = WIn * (1.f - WOut);

        AddShape(VisemeShapes().Find(Cur.Name), WCur * Cur.Weight * Amp * Fade, 1.f);
        if (Next)
        {
            AddShape(VisemeShapes().Find(Next->Name), WOut * Next->Weight * Amp * Fade, 1.f);
        }
    }
    else if (Curves.IsUsable())
    {
        // Visemesiz: og'iz to'g'ridan-to'g'ri egri chiziqlardan.
        const float F = Fade * (1.f - CurveClose * 0.85f);
        AddShape(VisemeShapes().Find(TEXT("aa")), CurveJaw * 0.8f * F, 1.f);
        AddShape(VisemeShapes().Find(TEXT("U")), CurveRound * 0.55f * F, 1.f);
        AddShape(VisemeShapes().Find(TEXT("I")), CurveSpread * 0.45f * F, 1.f);
    }

    if (Curves.IsUsable())
    {
        // Fuziya: audio QANCHA/QACHONligini boshqaradi.
        if (float* Jaw = CurveValues.Find(FName("jawOpen")))
        {
            *Jaw = *Jaw * (0.45f + 0.75f * CurveJaw) * (1.f - CurveClose * 0.85f);
        }
        CurveValues.FindOrAdd(FName("mouthClose")) += CurveClose * 0.55f * Fade;
        CurveValues.FindOrAdd(FName("mouthPucker")) += CurveRound * 0.3f * Fade;
        CurveValues.FindOrAdd(FName("mouthFunnel")) += CurveRound * 0.2f * Fade;
        CurveValues.FindOrAdd(FName("mouthStretchLeft")) += CurveSpread * 0.2f * Fade;
        CurveValues.FindOrAdd(FName("mouthStretchRight")) += CurveSpread * 0.2f * Fade;

        // Prosodiya -> qosh (renderer bilan bir xil koeffitsientlar).
        const float PitchUp = FMath::Max(0.f, LastPitch - 0.56f);
        const float PitchDown = FMath::Max(0.f, 0.42f - LastPitch);
        CurveValues.FindOrAdd(FName("browInnerUp")) += PitchUp * 0.55f * Fade;
        CurveValues.FindOrAdd(FName("browOuterUpLeft")) += PitchUp * 0.3f * Fade;
        CurveValues.FindOrAdd(FName("browOuterUpRight")) += PitchUp * 0.26f * Fade;
        CurveValues.FindOrAdd(FName("browDownLeft")) += PitchDown * 0.3f * Fade;
        CurveValues.FindOrAdd(FName("browDownRight")) += PitchDown * 0.28f * Fade;
    }

    const UWorld* World = GetWorld();
    const float Dt = World ? World->GetDeltaSeconds() : 0.016f;
    const float EnergyTarget = FMath::Max(CurveEnergy, 0.f);
    SmoothedEnergy += (EnergyTarget - SmoothedEnergy) * FMath::Min(1.f, Dt * 10.f);
}

void UCompanionLipSync::TickComponent(
    float DeltaTime,
    ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    LifeClock += DeltaTime; // idle noise/saccade uchun uzluksiz vaqt

    ResetCurves();

    MoodBlend = FMath::Min(1.f, MoodBlend + DeltaTime / FMath::Max(0.05f, MoodBlendSeconds));
    EvaluateMood();

    if (bJobActive)
    {
        Fade = FMath::Min(1.f, Fade + DeltaTime * 8.f);
        if (bClockRunning)
        {
            PlaybackSeconds += DeltaTime;
            if (PlaybackSeconds > JobDurationSeconds + 0.3f)
            {
                StopJob(); // Fade pastdagi else-shoxda silliq so'nadi
            }
        }
        EvaluateVisemes(PlaybackSeconds);
    }
    else
    {
        Fade = FMath::Max(0.f, Fade - DeltaTime * 6.f);
        SmoothedEnergy = FMath::Max(0.f, SmoothedEnergy - DeltaTime * 2.f);
    }

    // Idle "tiriklik" — gapirganda ham (siqilgan holda) ishlaydi.
    ApplyIdleGaze(DeltaTime);
    ApplyMicroExpression();
    ApplyAutoBlink(DeltaTime);
    ApplyIdleHead(DeltaTime);

    // Yakuniy clamp (faqat yuz curve'lari; bosh gradus qiymatlari alohida).
    for (TPair<FName, float>& Pair : CurveValues)
    {
        Pair.Value = FMath::Clamp(Pair.Value, 0.f, 1.f);
    }

    PushLiveLinkFrame();
}
