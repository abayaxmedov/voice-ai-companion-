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

namespace
{
    void ReadFloatArray(
        const TSharedPtr<FJsonObject>& Object,
        const TCHAR* FieldName,
        TArray<float>& Out)
    {
        const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
        if (!Object->TryGetArrayField(FieldName, Values) || !Values)
        {
            return;
        }
        Out.Reserve(Values->Num());
        for (const TSharedPtr<FJsonValue>& Value : *Values)
        {
            Out.Add(static_cast<float>(Value->AsNumber()));
        }
    }
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
        OnReadyReceived.Broadcast(ReadyAvatarId, ReadyPlayerUrl);
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

        // Fonema-aniq lab-sinxron ma'lumotlari.
        TArray<FCompanionVisemeFrame> Visemes;
        const TArray<TSharedPtr<FJsonValue>>* VisemeArray = nullptr;
        if ((*Payload)->TryGetArrayField(TEXT("visemes"), VisemeArray) && VisemeArray)
        {
            Visemes.Reserve(VisemeArray->Num());
            for (const TSharedPtr<FJsonValue>& Item : *VisemeArray)
            {
                const TSharedPtr<FJsonObject> Frame = Item->AsObject();
                if (!Frame.IsValid())
                {
                    continue;
                }
                FCompanionVisemeFrame Parsed;
                Parsed.TimeMs = static_cast<int32>(Frame->GetNumberField(TEXT("time_ms")));
                Frame->TryGetStringField(TEXT("name"), Parsed.Name);
                Parsed.Weight = static_cast<float>(Frame->GetNumberField(TEXT("weight")));
                Visemes.Add(MoveTemp(Parsed));
            }
        }

        FCompanionMouthCurves Curves;
        const TSharedPtr<FJsonObject>* CurvesObject = nullptr;
        if ((*Payload)->TryGetObjectField(TEXT("mouth_curves"), CurvesObject) && CurvesObject->IsValid())
        {
            Curves.Fps = static_cast<int32>((*CurvesObject)->GetNumberField(TEXT("fps")));
            ReadFloatArray(*CurvesObject, TEXT("energy"), Curves.Energy);
            ReadFloatArray(*CurvesObject, TEXT("jaw"), Curves.Jaw);
            ReadFloatArray(*CurvesObject, TEXT("close"), Curves.Close);
            ReadFloatArray(*CurvesObject, TEXT("spread"), Curves.Spread);
            ReadFloatArray(*CurvesObject, TEXT("round"), Curves.Round);
            ReadFloatArray(*CurvesObject, TEXT("pitch"), Curves.Pitch);
        }

        OnAvatarPlayEvent(TurnId, AudioRef, Mood, Behavior);
        OnAvatarPlayJob(TurnId, AudioRef, Mood, Behavior, Visemes, Curves);
        OnPlayJobReceived.Broadcast(TurnId, AudioRef, Mood, Behavior, Visemes, Curves);
        return;
    }

    if (Type == TEXT("avatar.state"))
    {
        FString State;
        (*Payload)->TryGetStringField(TEXT("state"), State);
        OnAvatarStateEvent(State);
        OnStateReceived.Broadcast(State);
        return;
    }

    if (Type == TEXT("avatar.interrupt"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        FString Reason;
        (*Payload)->TryGetStringField(TEXT("reason"), Reason);
        OnAvatarInterruptEvent(TurnId, Reason);
        OnInterruptReceived.Broadcast(TurnId, Reason);
        return;
    }

    if (Type == TEXT("avatar.completed"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        OnAvatarCompletedEvent(TurnId);
        OnCompletedReceived.Broadcast(TurnId);
        return;
    }

    if (Type == TEXT("avatar.error"))
    {
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);
        FString Message;
        (*Payload)->TryGetStringField(TEXT("message"), Message);
        OnAvatarErrorEvent(TurnId, Message);
        OnErrorReceived.Broadcast(TurnId, Message);
    }
}
