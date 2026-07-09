#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CompanionAvatarTypes.h"
#include "CompanionDirector.generated.h"

class UCompanionBridgePoller;
class UCompanionLipSync;

/**
 * Sahnadagi bridge "rejissyori" — Blueprint'siz to'liq ishlaydigan ulanish:
 *  - ichidagi CompanionBridgePoller 8770 bridge'ga ready yuborib hodisa poll qiladi;
 *  - BeginPlay'da sahnadan MetaHuman aktyorini topib unga CompanionLipSync
 *    komponentini runtime'da qo'shadi va poller hodisalarini C++ delegate'lar
 *    bilan unga ulaydi (avatar.play -> StartJob, interrupt -> StopJob, ...);
 *  - ko'rinishni sahnadagi birinchi CineCameraActor'ga o'tkazadi (retry bilan,
 *    chunki PlayerController biroz kechroq tug'ilishi mumkin) — Pixel Streaming
 *    aynan shu kadrni oqimlaydi.
 *
 * Qo'lda qoladigan yagona GUI ish: Face AnimBP'da Modify Curve tugunlari
 * (LipSync.GetCurveValue) — Docs/UNREAL_SETUP.md 7-bosqich.
 */
UCLASS(ClassGroup=(Companion))
class COMPANIONAVATAR_API ACompanionDirector : public AActor
{
    GENERATED_BODY()

public:
    ACompanionDirector();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Companion")
    TObjectPtr<UCompanionBridgePoller> BridgePoller;

    /** Runtime'da MetaHuman'ga qo'shilgan lab-sinxron komponenti. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Companion")
    TObjectPtr<UCompanionLipSync> LipSync;

    /** false bo'lsa view target o'zgartirilmaydi (masalan BP'da o'zingiz boshqarsangiz). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    bool bAutoViewTargetToCineCamera = true;

    /** Sahnadagi MetaHuman aktyorini nomi bo'yicha topish kaliti. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    FString MetaHumanActorNameContains = TEXT("MetaHuman");

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    FTimerHandle ViewTargetTimerHandle;
    FTimerHandle FaceValidateTimerHandle;
    FTimerHandle IdleLifeTimerHandle;
    int32 ViewTargetAttempts = 0;
    bool bFaceValidated = false;
    TWeakObjectPtr<AActor> MetaHumanActor;
    TWeakObjectPtr<USkeletalMeshComponent> FaceMesh;

    // Idle tiriklik validatsiyasi (nigoh + bosh suyagi rotatsiyasi o'lchanadi).
    int32 IdleProbeTicks = 0;
    float IdleGazeMax = 0.f;
    float IdleHeadSubjMax = 0.f;   // LipSync generatsiya qilgan gradus (biz)
    float IdleHeadBoneMax = 0.f;   // Face 'head' suyagi haqiqiy og'ishi (ABP natijasi)
    float IdleBreathMin = 1.f;     // nafas siklining eng past darajasi
    float IdleBreathMax = 0.f;     // nafas siklining eng yuqori darajasi
    bool bIdleHeadBaselineSet = false;
    FQuat IdleHeadBaseline = FQuat::Identity;

    // Validatsiya oynasi: gapirish davomida yig'ilgan maksimumlar.
    float ProbeOursMax = 0.f;
    float ProbeTheirsMax = 0.f;
    int32 ProbeTicks = 0;

    // Har job'da birinchi sync'ni bir marta log qilish uchun.
    bool bSyncLoggedThisJob = false;

    void AttachLipSyncToMetaHuman();

    /**
     * MetaHuman'ni ARKit/LiveLink rejimiga o'tkazadi: BP'dagi UseARKit/UseLiveLink
     * bayroqlarini yoqib, Face mesh'ning anim klassini tayyor ABP_MH_LiveLink'ka
     * almashtiradi. Shundan keyin LipSync push qilayotgan "LLink_Face_Subj"
     * subject'i yuz rigini boshqaradi — AnimBP'da qo'lda ish YO'Q.
     */
    void EnableArkitFaceMode(AActor* Actor);

    void TrySetViewTarget();

    /**
     * Gapirish boshlangach 1.5s o'tib Face AnimBP curve'ni LipSync qiymati
     * bilan solishtiradi: AnimBP 0 qaytarsa — Modify Curve hali ulanmagan
     * (docs/FACE_ANIMBP_STEPS.md), logda aniq ogohlantirish chiqadi.
     */
    void ValidateFaceCurves();

    /**
     * Idle "tiriklik" tekshiruvi: bir necha soniya davomida nigoh curve'lari,
     * saccade soni, LipSync bosh gradusi va Face 'head' suyagining haqiqiy
     * og'ishini o'lchab, "Idle tiriklik OK (...)" yoki muammoni logga yozadi.
     * Suyak og'ishi nol bo'lsa — HeadYaw/Pitch/Roll ABP'ga yetmayapti.
     */
    void ValidateIdleLife();

    UFUNCTION()
    void HandlePlayJob(
        const FString& TurnId,
        const FString& AudioRef,
        const FString& Mood,
        const FString& Behavior,
        const TArray<FCompanionVisemeFrame>& Visemes,
        const FCompanionMouthCurves& MouthCurves);

    UFUNCTION()
    void HandleState(const FString& State);

    UFUNCTION()
    void HandleSync(const FString& TurnId, float PositionSeconds);

    UFUNCTION()
    void HandleInterrupt(const FString& TurnId, const FString& Reason);
};
