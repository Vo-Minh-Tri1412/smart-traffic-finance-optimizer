using UnrealBuildTool;

public class TrafficRenderEditor : ModuleRules
{
    public TrafficRenderEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "TrafficRenderRuntime"
        });

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "CoreUObject",
            "Engine",
            "ProceduralMeshComponent",
            "UnrealEd"
        });
    }
}
