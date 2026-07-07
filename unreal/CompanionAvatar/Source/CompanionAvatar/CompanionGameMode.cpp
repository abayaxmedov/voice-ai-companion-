#include "CompanionGameMode.h"

#include "CompanionDirector.h"
#include "GameFramework/SpectatorPawn.h"
#include "Kismet/GameplayStatics.h"

ACompanionGameMode::ACompanionGameMode()
{
    DefaultPawnClass = ASpectatorPawn::StaticClass();
}

void ACompanionGameMode::StartPlay()
{
    Super::StartPlay();

    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    if (UGameplayStatics::GetActorOfClass(World, ACompanionDirector::StaticClass()))
    {
        return; // sahnada allaqachon bor
    }

    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    World->SpawnActor<ACompanionDirector>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
    UE_LOG(LogTemp, Log, TEXT("CompanionGameMode: CompanionDirector avtomatik spawn qilindi"));
}
