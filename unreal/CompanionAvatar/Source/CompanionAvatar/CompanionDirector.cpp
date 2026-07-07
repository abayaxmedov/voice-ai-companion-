#include "CompanionDirector.h"

#include "CineCameraActor.h"
#include "CompanionBridgePoller.h"
#include "CompanionLipSync.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

ACompanionDirector::ACompanionDirector()
{
    PrimaryActorTick.bCanEverTick = false;

    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    BridgePoller = CreateDefaultSubobject<UCompanionBridgePoller>(TEXT("BridgePoller"));
}

void ACompanionDirector::BeginPlay()
{
    Super::BeginPlay();

    BridgePoller->OnPlayJobReceived.AddDynamic(this, &ACompanionDirector::HandlePlayJob);
    BridgePoller->OnStateReceived.AddDynamic(this, &ACompanionDirector::HandleState);
    BridgePoller->OnInterruptReceived.AddDynamic(this, &ACompanionDirector::HandleInterrupt);

    AttachLipSyncToMetaHuman();

    if (bAutoViewTargetToCineCamera)
    {
        GetWorldTimerManager().SetTimer(
            ViewTargetTimerHandle,
            this,
            &ACompanionDirector::TrySetViewTarget,
            0.25f,
            true,
            0.f
        );
    }
}

void ACompanionDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    GetWorldTimerManager().ClearTimer(ViewTargetTimerHandle);
    Super::EndPlay(EndPlayReason);
}

void ACompanionDirector::AttachLipSyncToMetaHuman()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor->GetName().Contains(MetaHumanActorNameContains))
        {
            continue;
        }
        if (!Actor->FindComponentByClass<USkeletalMeshComponent>())
        {
            continue;
        }

        LipSync = NewObject<UCompanionLipSync>(Actor, TEXT("CompanionLipSync"));
        LipSync->RegisterComponent();
        UE_LOG(LogTemp, Log, TEXT("CompanionDirector: LipSync -> %s"), *Actor->GetName());
        return;
    }

    UE_LOG(LogTemp, Warning,
        TEXT("CompanionDirector: '%s' nomli MetaHuman aktyori topilmadi — lab-sinxron o'chiq"),
        *MetaHumanActorNameContains);
}

void ACompanionDirector::TrySetViewTarget()
{
    ++ViewTargetAttempts;
    UWorld* World = GetWorld();
    APlayerController* Controller = World ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;

    if (Controller)
    {
        if (AActor* Camera = UGameplayStatics::GetActorOfClass(World, ACineCameraActor::StaticClass()))
        {
            Controller->SetViewTargetWithBlend(Camera, 0.0f);
            UE_LOG(LogTemp, Log, TEXT("CompanionDirector: view target -> %s"), *Camera->GetName());
            GetWorldTimerManager().ClearTimer(ViewTargetTimerHandle);
            return;
        }
    }

    // ~10 soniyadan keyin urinishni to'xtatamiz (kamera yo'q sahna ham yashasin).
    if (ViewTargetAttempts >= 40)
    {
        UE_LOG(LogTemp, Warning, TEXT("CompanionDirector: CineCameraActor/PlayerController topilmadi"));
        GetWorldTimerManager().ClearTimer(ViewTargetTimerHandle);
    }
}

void ACompanionDirector::HandlePlayJob(
    const FString& TurnId,
    const FString& AudioRef,
    const FString& Mood,
    const FString& Behavior,
    const TArray<FCompanionVisemeFrame>& Visemes,
    const FCompanionMouthCurves& MouthCurves)
{
    if (!LipSync)
    {
        return;
    }

    LipSync->StartJob(Visemes, MouthCurves, Mood);
    // Audio Electron tomonida ijro etiladi — hodisa kelgan zahoti boshlaymiz;
    // drift sezilsa keyinchalik SyncPlaybackTime bilan tuzatiladi.
    LipSync->StartPlayback();
}

void ACompanionDirector::HandleState(const FString& State)
{
    if (LipSync)
    {
        LipSync->SetCompanionState(State);
    }
}

void ACompanionDirector::HandleInterrupt(const FString& TurnId, const FString& Reason)
{
    if (LipSync)
    {
        LipSync->StopJob();
    }
}
