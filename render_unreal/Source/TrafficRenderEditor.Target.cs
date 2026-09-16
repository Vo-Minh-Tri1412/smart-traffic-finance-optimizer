using UnrealBuildTool;

public class TrafficRenderEditorTarget : TargetRules
{
    public TrafficRenderEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("TrafficRender");
    }
}
