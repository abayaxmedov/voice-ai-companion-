#pragma once

#include "CoreMinimal.h"
#include "ILiveLinkSource.h"

/**
 * Minimal in-process LiveLink manbasi: UCompanionLipSync har tick ARKit curve
 * qiymatlarini shu manba nomidan "LLink_Face_Subj" subject'iga push qiladi.
 * MetaHuman'ning tayyor ABP_MH_LiveLink yuz rigi shu subject'ni o'qiydi —
 * AnimBP'ni qo'lda tahrirlash SHART EMAS.
 */
class FCompanionLiveLinkSource : public ILiveLinkSource
{
public:
    virtual void ReceiveClient(ILiveLinkClient* InClient, FGuid InSourceGuid) override
    {
        Client = InClient;
        SourceGuid = InSourceGuid;
    }

    virtual bool IsSourceStillValid() const override { return true; }
    virtual bool RequestSourceShutdown() override { return true; }

    virtual FText GetSourceType() const override
    {
        return NSLOCTEXT("Companion", "SourceType", "Companion LipSync");
    }

    virtual FText GetSourceMachineName() const override
    {
        return NSLOCTEXT("Companion", "SourceMachine", "local");
    }

    virtual FText GetSourceStatus() const override
    {
        return NSLOCTEXT("Companion", "SourceStatus", "Active");
    }

    FGuid GetSourceGuid() const { return SourceGuid; }

private:
    ILiveLinkClient* Client = nullptr;
    FGuid SourceGuid;
};
