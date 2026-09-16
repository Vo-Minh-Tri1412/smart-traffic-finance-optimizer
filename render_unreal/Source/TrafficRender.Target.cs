using UnrealBuildTool;

public class TrafficRenderTarget : TargetRules
{
    public TrafficRenderTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("TrafficRender");
    }
}
