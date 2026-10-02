using UnrealBuildTool;

public class TrafficRenderRuntime : ModuleRules
{
    public TrafficRenderRuntime(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "ProceduralMeshComponent"
        });

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Json",
            "JsonUtilities",
            "Projects",
            "XmlParser",
            "Sockets",
            "Networking",
            "InputCore"
        });
    }
}
