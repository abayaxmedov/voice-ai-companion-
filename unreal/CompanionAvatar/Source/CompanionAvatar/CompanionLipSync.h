#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CompanionAvatarTypes.h"
#include "CompanionLipSync.generated.h"

/**
 * Fonema-aniq lab-sinxron evaluatori (renderer'dagi avatar3d.js mantiqning
 * UE porti): viseme timeline + audio-tahlil egri chiziqlarini har tick'da
 * ARKit curve qiymatlariga aylantiradi.
 *
 * Ishlatish (Blueprint):
 *  1. MetaHuman aktyoriga shu komponentni qo'shing.
 *  2. CompanionBridgePoller.OnAvatarPlayJob -> StartJob(...).
 *  3. Audio HAQIQATAN boshlangan kadrda StartPlayback() chaqiring
 *     (kerak bo'lsa har 1-2 soniyada SyncPlaybackTime(AudioComponent vaqti)).
 *  4. Face AnimBP AnimGraph'ida Modify Curve tugunlari bilan
 *     GetCurveValue("jawOpen") va hokazo qiymatlarni yozing — nomlar ARKit
 *     standartida, MetaHuman ARKit mapping'i bilan bir xil:
 *     jawOpen, mouthClose, mouthFunnel, mouthPucker, mouthSmileLeft/Right,
 *     mouthStretchLeft/Right, mouthPressLeft/Right, mouthShrugUpper/Lower,
 *     mouthLowerDownLeft/Right, mouthUpperUpLeft/Right, mouthDimpleLeft/Right,
 *     mouthFrownLeft/Right, mouthRollUpper/Lower, mouthLeft,
 *     browInnerUp, browDownLeft/Right, browOuterUpLeft/Right,
 *     eyeSquintLeft/Right, eyeWideLeft/Right, cheekSquintLeft/Right, jawForward.
 *  5. avatar.interrupt -> StopJob(); avatar.state -> SetCompanionState().
 */
UCLASS(ClassGroup=(Companion), meta=(BlueprintSpawnableComponent))
class COMPANIONAVATAR_API UCompanionLipSync : public UActorComponent
{
    GENERATED_BODY()

public:
    UCompanionLipSync();

    /** Kayfiyat o'tish davomiyligi (renderer bilan bir xil: 300ms). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion LipSync")
    float MoodBlendSeconds = 0.3f;

    /** Gapirganda mood og'iz morphlari shu koeffitsientgacha pasayadi. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion LipSync")
    float SpeakingMouthMoodScale = 0.4f;

    /**
     * Curve'larni LiveLink subject sifatida push qilish — MetaHuman'ning
     * tayyor ABP_MH_LiveLink yuz rigi (UseARKit rejimi) shuni o'qiydi,
     * AnimBP'da qo'lda Modify Curve ulash shart bo'lmaydi.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion LipSync|LiveLink")
    bool bPushLiveLink = true;

    /** BP_NewMetaHumanCharacter'dagi standart subject nomi. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion LipSync|LiveLink")
    FName LiveLinkSubjectName = TEXT("LLink_Face_Subj");

    /** Tabiiylik uchun avtomatik ko'z pirpirashi (eyeBlinkLeft/Right). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion LipSync")
    bool bAutoBlink = true;

    // --- Idle "tiriklik": nigoh, mikro-mimika (bosh alohida Director'da). ---

    /** Idle ko'z nigohi (saccade + drift) — personaj tikilib qotmasin. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    bool bEnableIdleGaze = true;

    /** Nigoh maksimal og'ishi (0..1 ARKit eyeLook birligida; ~0.35 tabiiy). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    float GazeAmplitude = 0.35f;

    /** Gapirganda nigoh shu koeffitsientga siqiladi (odam markazga ko'proq qaraydi). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    float SpeakingGazeScale = 0.45f;

    /** Idle yuz mikro-mimikasi (sekin brow/smile/cheek drift). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    bool bEnableMicroExpression = true;

    /** Mikro-mimika amplitudasi (~0.05 — sezilmas, "nafas oladigan" yuz). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    float MicroExpressionAmplitude = 0.05f;

    // --- Bosh harakati (yuz subjecti orqali HeadYaw/Pitch/Roll, gradus). ---
    // MetaHuman ABP_MH_LiveLink shu 3 xossani o'sha yuz subjectidan o'qib
    // (HeadControlSwitch/LLink_Face_Head gate'lari bilan) bosh suyagini buradi.
    // Gradus qiymatlari [0,1] clamp'dan chetlab o'tadi (alohida saqlanadi).

    /** Idle bosh tebranishi (Perlin sway + nutq urg'usi). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    bool bEnableIdleHead = true;

    /** Idle bosh amplitudasi (HAQIQIY gradus; yaw uchun ~2.5°, roll yarmi). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    float HeadAmplitudeDeg = 2.5f;

    /** Gapirganda bosh urg'usi kuchi (nutq energiyasiga ko'paytiriladi, gradus). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    float SpeakingHeadEmphasisDeg = 3.0f;

    /**
     * ABP HeadYaw/Pitch/Roll birligini nechta gradus bosh burilishiga aylantiradi
     * (o'lchangan: HeadYaw=10 -> bosh yaw ~140°, ya'ni ~14°/birlik). HAQIQIY
     * gradus qiymati shunga bo'linib LiveLink'ka uzatiladi. Vizual tekshiruvda
     * (2.6) sozlanishi mumkin.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Idle")
    float HeadDegPerUnit = 14.0f;

    UFUNCTION(BlueprintPure, Category="Companion Idle")
    float GetHeadYaw() const { return HeadYawDeg; }
    UFUNCTION(BlueprintPure, Category="Companion Idle")
    float GetHeadPitch() const { return HeadPitchDeg; }
    UFUNCTION(BlueprintPure, Category="Companion Idle")
    float GetHeadRoll() const { return HeadRollDeg; }

    /** Idle nigoh joriy og'ishi (validatsiya/diagnostika uchun, 0..1). */
    UFUNCTION(BlueprintPure, Category="Companion Idle")
    float GetGazeMagnitude() const { return FMath::Sqrt(GazeCurrent.X * GazeCurrent.X + GazeCurrent.Y * GazeCurrent.Y); }

    /** Boshlanishdan beri saccade (nigoh sakrashi) soni. */
    UFUNCTION(BlueprintPure, Category="Companion Idle")
    int32 GetSaccadeCount() const { return SaccadeCount; }

    UFUNCTION(BlueprintCallable, Category="Companion LipSync")
    void StartJob(
        const TArray<FCompanionVisemeFrame>& Visemes,
        const FCompanionMouthCurves& MouthCurves,
        const FString& Mood
    );

    /** Audio ijrosi haqiqatan boshlanganda chaqiring (ichki soat 0 dan). */
    UFUNCTION(BlueprintCallable, Category="Companion LipSync")
    void StartPlayback();

    /** Drift tuzatish: AudioComponent'dan haqiqiy ijro vaqti (soniya). */
    UFUNCTION(BlueprintCallable, Category="Companion LipSync")
    void SyncPlaybackTime(float PlaybackSeconds);

    UFUNCTION(BlueprintCallable, Category="Companion LipSync")
    void StopJob();

    UFUNCTION(BlueprintCallable, Category="Companion LipSync")
    void SetMood(const FString& Mood);

    /** idle | listening | thinking | speaking | error */
    UFUNCTION(BlueprintCallable, Category="Companion LipSync")
    void SetCompanionState(const FString& State);

    /** AnimBP uchun: ARKit curve qiymati (0..1). */
    UFUNCTION(BlueprintPure, Category="Companion LipSync")
    float GetCurveValue(FName CurveName) const;

    /** Bosh ta'kidlari uchun silliqlangan nutq energiyasi (0..1). */
    UFUNCTION(BlueprintPure, Category="Companion LipSync")
    float GetSpeechEnergy() const { return SmoothedEnergy; }

    UFUNCTION(BlueprintPure, Category="Companion LipSync")
    bool IsSpeaking() const { return bJobActive; }

    /** Prosodiya: joriy pitch og'ishi (0.5 = neytral). */
    UFUNCTION(BlueprintPure, Category="Companion LipSync")
    float GetPitch() const { return LastPitch; }

    // --- AnimBP qulayligi: har bir ARKit curve uchun alohida getter. ---
    // Face AnimBP'da Modify Curve pinini Property Access bilan to'g'ridan-to'g'ri
    // shu getterlarga ulash mumkin (o'zgaruvchi/Set tugunlari shart emas).
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetJawOpen() const { return GetCurveValue(TEXT("jawOpen")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthClose() const { return GetCurveValue(TEXT("mouthClose")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthFunnel() const { return GetCurveValue(TEXT("mouthFunnel")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthPucker() const { return GetCurveValue(TEXT("mouthPucker")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthSmileLeft() const { return GetCurveValue(TEXT("mouthSmileLeft")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthSmileRight() const { return GetCurveValue(TEXT("mouthSmileRight")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthStretchLeft() const { return GetCurveValue(TEXT("mouthStretchLeft")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetMouthStretchRight() const { return GetCurveValue(TEXT("mouthStretchRight")); }
    UFUNCTION(BlueprintPure, Category="Companion LipSync|Curves")
    float GetBrowInnerUp() const { return GetCurveValue(TEXT("browInnerUp")); }

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(
        float DeltaTime,
        ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction
    ) override;

private:
    // Ijro holati.
    bool bJobActive = false;
    bool bClockRunning = false;
    float PlaybackSeconds = 0.f;
    float JobDurationSeconds = 0.f;
    float Fade = 0.f;
    int32 FrameIndex = 0;
    TArray<FCompanionVisemeFrame> Frames;
    FCompanionMouthCurves Curves;

    // Kayfiyat.
    FString CurrentMood = TEXT("neutral");
    FString PreviousMood = TEXT("neutral");
    float MoodBlend = 1.f;
    FString CompanionState = TEXT("idle");

    // Chiqish.
    TMap<FName, float> CurveValues;
    float SmoothedEnergy = 0.f;
    float LastPitch = 0.5f;

    // Avto-pirpirash holati.
    float BlinkCooldown = 1.5f;
    float BlinkPhase = -1.f; // <0: pirpirash yo'q; 0..1: jarayonda
    int32 BlinkBurstLeft = 0; // ketma-ket qo'sh pirpirash uchun

    // Idle nigoh holati.
    FVector2D GazeCurrent = FVector2D::ZeroVector; // X: o'ng(+)/chap(-), Y: yuqori(+)/past(-)
    FVector2D GazeTarget = FVector2D::ZeroVector;
    float GazeTimer = 0.6f;      // keyingi saccadegacha
    int32 SaccadeCount = 0;
    float NoiseSeed = 0.f;       // shu instansiya uchun mikro-mimika fazasi
    double LifeClock = 0.0;      // uzluksiz idle vaqti (noise uchun)

    // Bosh pozitsiyasi (gradus; clamp'siz LiveLink'ga uzatiladi).
    float HeadYawDeg = 0.f;
    float HeadPitchDeg = 0.f;
    float HeadRollDeg = 0.f;

    // LiveLink.
    TSharedPtr<class FCompanionLiveLinkSource> LiveLinkSource;
    class ILiveLinkClient* LiveLinkClient = nullptr;
    // Subject xossa nomlari (FName case-insensitive — PoseAsset nomlariga mos).
    TArray<FName> LiveLinkPropertyNames;

    void SetupLiveLink();
    void TeardownLiveLink();
    void PushLiveLinkFrame();
    void ApplyAutoBlink(float DeltaTime);
    void ApplyIdleGaze(float DeltaTime);
    void ApplyMicroExpression();
    void ApplyIdleHead(float DeltaTime);

    void ResetCurves();
    void AddShape(const TArray<TPair<FName, float>>* Shape, float Multiplier, float MouthScale);
    void EvaluateVisemes(float TimeSeconds);
    void EvaluateMood();

    static const TMap<FString, TArray<TPair<FName, float>>>& VisemeShapes();
    static const TMap<FString, TArray<TPair<FName, float>>>& MoodShapes();
    static bool IsMouthCurve(FName CurveName);
};
