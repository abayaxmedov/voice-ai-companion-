using UnrealBuildTool;
using System.Collections.Generic;

public class CompanionAvatarEditorTarget : TargetRules
{
    public CompanionAvatarEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("CompanionAvatar");
    }
}

