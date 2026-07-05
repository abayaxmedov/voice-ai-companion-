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

protected:
    virtual void BeginPlay() override;
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

    void ResetCurves();
    void AddShape(const TArray<TPair<FName, float>>* Shape, float Multiplier, float MouthScale);
    void EvaluateVisemes(float TimeSeconds);
    void EvaluateMood();

    static const TMap<FString, TArray<TPair<FName, float>>>& VisemeShapes();
    static const TMap<FString, TArray<TPair<FName, float>>>& MoodShapes();
    static bool IsMouthCurve(FName CurveName);
};
