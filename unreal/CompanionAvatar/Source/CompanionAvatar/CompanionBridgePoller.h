#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CompanionAvatarTypes.h"
#include "CompanionBridgePoller.generated.h"

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

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion Bridge")
    FString PlayerUrl = TEXT("http://127.0.0.1:8888");

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
