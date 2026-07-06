using UnrealBuildTool;
using System.Collections.Generic;

public class CompanionAvatarTarget : TargetRules
{
    public CompanionAvatarTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        // "Latest" — har qanday UE versiyasida (5.7, 5.8...) o'sha versiyaning
        // eng yangi sozlamalarini oladi; V7 kabi qat'iy raqam eski versiyada yo'q.
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("CompanionAvatar");
    }
}

