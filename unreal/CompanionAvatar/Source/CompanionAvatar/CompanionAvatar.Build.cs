using UnrealBuildTool;

public class CompanionAvatar : ModuleRules
{
    public CompanionAvatar(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "CinematicCamera",
            "LiveLinkInterface",
            "HTTP",
            "Json",
            "JsonUtilities"
        });
    }
}

