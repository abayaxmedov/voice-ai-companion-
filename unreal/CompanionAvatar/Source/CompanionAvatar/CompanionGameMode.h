#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "CompanionGameMode.generated.h"

/**
 * Standart o'yin rejimi (DefaultEngine.ini GlobalDefaultGameMode):
 *  - pawn sifatida ko'rinmas SpectatorPawn (WASD bilan uchib yurmaydi ham —
 *    baribir view target CineCamera'da qoladi);
 *  - StartPlay'da sahnada ACompanionDirector bo'lmasa o'zi spawn qiladi.
 * Shu tufayli foydalanuvchi levelga hech narsa qo'ymasa ham bridge + lab-sinxron
 * + kamera oqimi ishlayveradi.
 */
UCLASS()
class COMPANIONAVATAR_API ACompanionGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    ACompanionGameMode();

    virtual void StartPlay() override;
};
