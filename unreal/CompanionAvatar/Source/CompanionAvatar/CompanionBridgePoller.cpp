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
    GetWorld()->GetTimerManager().SetTimer(
        PollTimerHandle,
        this,
        &UCompanionBridgePoller::PollEvents,
        PollIntervalSeconds,
        true
    );
    // Ready e'loni tasdiqlangunga qadar har 2 soniyada takrorlanadi — UE
    // bridge'dan oldin ochilsa yoki bridge qayta ishga tushsa ham tiklanadi.
    GetWorld()->GetTimerManager().SetTimer(
        ReadyTimerHandle,
        this,
        &UCompanionBridgePoller::AnnounceReady,
        2.0f,
        true,
        0.f
    );
}

void UCompanionBridgePoller::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (GetWorld())
    {
        GetWorld()->GetTimerManager().ClearTimer(PollTimerHandle);
        GetWorld()->GetTimerManager().ClearTimer(ReadyTimerHandle);
    }
    Super::EndPlay(EndPlayReason);
}

void UCompanionBridgePoller::AnnounceReady()
{
    if (bReadyAcknowledged)
    {
        return;
    }

    TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
    Payload->SetStringField(TEXT("avatar_id"), AvatarId);
    Payload->SetStringField(TEXT("player_url"), PlayerUrl);

    FString Body;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(Payload, Writer);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(ReadyUrl);
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Request->SetContentAsString(Body);
    TWeakObjectPtr<UCompanionBridgePoller> WeakThis(this);
    Request->OnProcessRequestComplete().BindLambda(
        [WeakThis](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
        {
            if (!WeakThis.IsValid() || !bSucceeded || !Response.IsValid())
            {
                return;
            }
            const int32 Code = Response->GetResponseCode();
            if (Code >= 200 && Code < 300)
            {
                WeakThis->bReadyAcknowledged = true;
                UE_LOG(LogTemp, Log, TEXT("Companion bridge: ready tasdiqlandi (player_url=%s)"),
                    *WeakThis->PlayerUrl);
            }
        }
    );
    Request->ProcessRequest();
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
            if (!WeakThis.IsValid())
            {
                return;
            }
            if (!bSucceeded || !Response.IsValid())
            {
                // Bridge yiqildi/qayta ishga tushdi — ready'ni qayta e'lon qilamiz.
                WeakThis->bReadyAcknowledged = false;
                return;
            }

            const int32 ResponseCode = Response->GetResponseCode();
            if (ResponseCode < 200 || ResponseCode >= 300)
            {
                WeakThis->bReadyAcknowledged = false;
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

    if (Type == TEXT("avatar.sync"))
    {
        double PositionMs = 0.0;
        (*Payload)->TryGetNumberField(TEXT("position_ms"), PositionMs);
        FString TurnId;
        (*Payload)->TryGetStringField(TEXT("turn_id"), TurnId);

        // Hodisa yaratilgandan beri o'tgan vaqtni qo'shamiz (bridge va UE bir
        // mashinada — soatlar bir xil); poll kechikishi shu bilan yo'qoladi.
        double LatencyMs = 0.0;
        FString CreatedAt;
        FDateTime Created;
        if (EventObject->TryGetStringField(TEXT("created_at"), CreatedAt)
            && FDateTime::ParseIso8601(*CreatedAt, Created))
        {
            LatencyMs = FMath::Clamp(
                (FDateTime::UtcNow() - Created).GetTotalMilliseconds(), 0.0, 1000.0);
        }

        const float PositionSeconds = static_cast<float>((PositionMs + LatencyMs) / 1000.0);
        OnAvatarSyncEvent(TurnId, PositionSeconds);
        OnSyncReceived.Broadcast(TurnId, PositionSeconds);
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
