#include "CompanionBridgePoller.h"

#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "TimerManager.h"

UCompanionBridgePoller::UCompanionBridgePoller()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UCompanionBridgePoller::BeginPlay()
{
    Super::BeginPlay();
    PollIntervalSeconds = FMath::Max(0.05f, PollIntervalSeconds);
    AnnounceReady();
    GetWorld()->GetTimerManager().SetTimer(
        PollTimerHandle,
        this,
        &UCompanionBridgePoller::PollEvents,
        PollIntervalSeconds,
        true
    );
}

void UCompanionBridgePoller::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (GetWorld())
    {
        GetWorld()->GetTimerManager().ClearTimer(PollTimerHandle);
    }
    Super::EndPlay(EndPlayReason);
}

void UCompanionBridgePoller::AnnounceReady()
{
    TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
    Payload->SetStringField(TEXT("avatar_id"), AvatarId);
    Payload->SetStringField(TEXT("player_url"), PlayerUrl);
    SendJsonPost(ReadyUrl, Payload);
}

void UCompanionBridgePoller::SendJsonPost(const FString& Url, const TSharedRef<FJsonObject>& Payload) const
{
    FString Body;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(Payload, Writer);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(Url);
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Request->SetContentAsString(Body);
    Request->ProcessRequest();
}

void UCompanionBridgePoller::PollEvents()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BridgeEventsUrl);
    Request->SetVerb(TEXT("GET"));
    TWeakObjectPtr<UCompanionBridgePoller> WeakThis(this);
    Request->OnProcessRequestComplete().BindLambda(
        [WeakThis](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
        {
            if (!WeakThis.IsValid() || !bSucceeded || !Response.IsValid())
            {
                return;
            }

            const int32 ResponseCode = Response->GetResponseCode();
            if (ResponseCode < 200 || ResponseCode >= 300)
            {
                return;
            }

            TSharedPtr<FJsonObject> Root;
            TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
            if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
            {
                return;
            }

            const TArray<TSharedPtr<FJsonValue>>* Events;
            if (!Root->TryGetArrayField(TEXT("events"), Events))
            {
                return;
            }

            for (const TSharedPtr<FJsonValue>& Value : *Events)
            {
                WeakThis->HandleEventObject(Value->AsObject());
            }
        }
    );
    Request->ProcessRequest();
}

void UCompanionBridgePoller::HandleEventObject(const TSharedPtr<FJsonObject>& EventObject)
{
    if (!EventObject.IsValid())
    {
        return;
    }

    FString Type;
    if (!EventObject->TryGetStringField(TEXT("type"), Type))
    {
        return;
    }

    if (bLogBridgeEvents)
    {
        UE_LOG(LogTemp, Log, TEXT("Companion bridge event: %s"), *Type);
    }

    const TSharedPtr<FJsonObject>* Payload;
    if (!EventObject->TryGetObjectField(TEXT("payload"), Payload) || !Payload->IsValid())
    {
        return;
    }

    if (Type == TEXT("avatar.ready"))
    {
        FString ReadyAvatarId;
        (*Payload)->TryGetStringField(TEXT("avatar_id"), ReadyAvatarId);
        FString ReadyPlayerUrl;
        (*Payload)->TryGetStringField(TEXT("player_url"), ReadyPlayerUrl);
        OnAvatarReadyEvent(ReadyAvatarId, ReadyPlayerUrl);
        return;
    }

    if (Type == TEXT("avatar.play"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        FString AudioRef;
        (*Payload)->TryGetStringField(TEXT("audio_ref"), AudioRef);
        FString Mood;
        (*Payload)->TryGetStringField(TEXT("mood"), Mood);
        FString Behavior;
        (*Payload)->TryGetStringField(TEXT("behavior"), Behavior);
        OnAvatarPlayEvent(
            TurnId,
            AudioRef,
            Mood,
            Behavior
        );
        return;
    }

    if (Type == TEXT("avatar.state"))
    {
        FString State;
        (*Payload)->TryGetStringField(TEXT("state"), State);
        OnAvatarStateEvent(State);
        return;
    }

    if (Type == TEXT("avatar.interrupt"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        FString Reason;
        (*Payload)->TryGetStringField(TEXT("reason"), Reason);
        OnAvatarInterruptEvent(TurnId, Reason);
        return;
    }

    if (Type == TEXT("avatar.completed"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        OnAvatarCompletedEvent(TurnId);
        return;
    }

    if (Type == TEXT("avatar.error"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        FString Message;
        (*Payload)->TryGetStringField(TEXT("message"), Message);
        OnAvatarErrorEvent(TurnId, Message);
    }
}
