#include "CompanionLipSync.h"

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

    ResetCurves();

    MoodBlend = FMath::Min(1.f, MoodBlend + DeltaTime / FMath::Max(0.05f, MoodBlendSeconds));
    EvaluateMood();

    if (bJobActive)
    {
        Fade = FMath::Min(1.f, Fade + DeltaTime * 8.f);
        if (bClockRunning)
        {
            PlaybackSeconds += DeltaTime;
        }
        EvaluateVisemes(PlaybackSeconds);
    }
    else
    {
        Fade = FMath::Max(0.f, Fade - DeltaTime * 6.f);
        SmoothedEnergy = FMath::Max(0.f, SmoothedEnergy - DeltaTime * 2.f);
    }

    // Yakuniy clamp.
    for (TPair<FName, float>& Pair : CurveValues)
    {
        Pair.Value = FMath::Clamp(Pair.Value, 0.f, 1.f);
    }
}
