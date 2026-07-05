#pragma once

#include "CoreMinimal.h"
#include "CompanionAvatarTypes.generated.h"

/** Backend viseme kadri: qaysi og'iz shakli, qachon, qancha kuch bilan. */
USTRUCT(BlueprintType)
struct COMPANIONAVATAR_API FCompanionVisemeFrame
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    int32 TimeMs = 0;

    /** Oculus/ARKit viseme klassi: sil PP FF DD kk CH SS nn RR aa E I O U */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    FString Name = TEXT("sil");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    float Weight = 0.f;
};

/** Backend audio-tahlili (50fps egri chiziqlar, 0..1). */
USTRUCT(BlueprintType)
struct COMPANIONAVATAR_API FCompanionMouthCurves
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    int32 Fps = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    TArray<float> Energy;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    TArray<float> Jaw;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    TArray<float> Close;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    TArray<float> Spread;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    TArray<float> Round;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Companion")
    TArray<float> Pitch;

    bool IsUsable() const { return Fps > 0 && Jaw.Num() > 0; }

    float Sample(const TArray<float>& Curve, float TimeSeconds) const
    {
        if (Curve.Num() == 0 || Fps <= 0)
        {
            return 0.f;
        }
        const float Pos = TimeSeconds * static_cast<float>(Fps);
        const int32 Index = FMath::Clamp(FMath::FloorToInt32(Pos), 0, Curve.Num() - 1);
        const int32 Next = FMath::Min(Index + 1, Curve.Num() - 1);
        const float Frac = FMath::Clamp(Pos - static_cast<float>(Index), 0.f, 1.f);
        return FMath::Lerp(Curve[Index], Curve[Next], Frac);
    }
};
