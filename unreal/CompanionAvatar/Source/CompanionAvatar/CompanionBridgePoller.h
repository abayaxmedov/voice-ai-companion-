#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CompanionAvatarTypes.h"
#include "CompanionBridgePoller.generated.h"

/**
 * BIE (BlueprintImplementableEvent) hodisalarning C++/BP'dan ulanadigan
 * delegate ko'rinishlari: BIE faqat Blueprint subclass'da implement qilinadi,
 * delegate esa AddDynamic bilan istalgan joydan (masalan ACompanionDirector)
 * ulanadi. Ikkalasi ham bir vaqtda fire bo'ladi.
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FCompanionReadySignature, const FString&, AvatarId, const FString&, PlayerUrl);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_SixParams(FCompanionPlayJobSignature, const FString&, TurnId, const FString&, AudioRef, const FString&, Mood, const FString&, Behavior, const TArray<FCompanionVisemeFrame>&, Visemes, const FCompanionMouthCurves&, MouthCurves);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCompanionStateSignature, const FString&, State);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FCompanionInterruptSignature, const FString&, TurnId, const FString&, Reason);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCompanionCompletedSignature, const FString&, TurnId);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FCompanionErrorSignature, const FString&, TurnId, const FString&, Message);

UCLASS(ClassGroup=(Companion), meta=(BlueprintSpawnableComponent))
class COMPANIONAVATAR_API UCompanionBridgePoller : public UActorComponent
{
    GENERATED_BODY()

public:
    UCompanionBridgePoller();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    FString BridgeEventsUrl = TEXT("http://127.0.0.1:8770/avatar/events?mode=poll");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    FString ReadyUrl = TEXT("http://127.0.0.1:8770/avatar/ready");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    FString AvatarId = TEXT("metahuman_default");

    /** Pixel Streaming player sahifasi (signalling server HTTP porti, sukut 80) — Electron shu URLni iframe qiladi. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    FString PlayerUrl = TEXT("http://127.0.0.1:80");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    float PollIntervalSeconds = 0.25f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    bool bLogBridgeEvents = true;

    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarReadyEvent(const FString& ReadyAvatarId, const FString& ReadyPlayerUrl);

    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarPlayEvent(const FString& TurnId, const FString& AudioRef, const FString& Mood, const FString& Behavior);

    /**
     * To'liq ijro topshirig'i: viseme timeline + audio-tahlil egri chiziqlari
     * bilan. Lab-sinxron uchun shu hodisani UCompanionLipSync::StartJob ga
     * ulang (OnAvatarPlayEvent eski/sodda variant sifatida qoladi).
     */
    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarPlayJob(
        const FString& TurnId,
        const FString& AudioRef,
        const FString& Mood,
        const FString& Behavior,
        const TArray<FCompanionVisemeFrame>& Visemes,
        const FCompanionMouthCurves& MouthCurves
    );

    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarStateEvent(const FString& State);

    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarInterruptEvent(const FString& TurnId, const FString& Reason);

    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarCompletedEvent(const FString& TurnId);

    UFUNCTION(BlueprintImplementableEvent, Category="Companion Bridge")
    void OnAvatarErrorEvent(const FString& TurnId, const FString& Message);

    UPROPERTY(BlueprintAssignable, Category="Companion Bridge")
    FCompanionReadySignature OnReadyReceived;

    UPROPERTY(BlueprintAssignable, Category="Companion Bridge")
    FCompanionPlayJobSignature OnPlayJobReceived;

    UPROPERTY(BlueprintAssignable, Category="Companion Bridge")
    FCompanionStateSignature OnStateReceived;

    UPROPERTY(BlueprintAssignable, Category="Companion Bridge")
    FCompanionInterruptSignature OnInterruptReceived;

    UPROPERTY(BlueprintAssignable, Category="Companion Bridge")
    FCompanionCompletedSignature OnCompletedReceived;

    UPROPERTY(BlueprintAssignable, Category="Companion Bridge")
    FCompanionErrorSignature OnErrorReceived;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    FTimerHandle PollTimerHandle;

    void AnnounceReady();
    void PollEvents();
    void HandleEventObject(const TSharedPtr<FJsonObject>& EventObject);
    void SendJsonPost(const FString& Url, const TSharedRef<FJsonObject>& Payload) const;
};
