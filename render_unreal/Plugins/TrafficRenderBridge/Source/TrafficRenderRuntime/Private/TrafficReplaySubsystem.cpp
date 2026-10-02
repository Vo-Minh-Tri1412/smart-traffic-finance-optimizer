#include "TrafficReplaySubsystem.h"

#include "Misc/FileHelper.h"
#include "TrafficRenderManifest.h"

bool UTrafficReplaySubsystem::LoadRenderRun(const FString& ManifestPath, const int32 MaxFrames, FString& OutError)
{
    QaSummary = FTrafficReplayQaSummary();
    Manifest = FTrafficRenderRunManifest();
    Geometry = FTrafficGeometryManifest();
    Trace = FTrafficVehicleTrace();
    CurrentFrame = FTrafficVehicleTraceFrame();
    TArray<FString> Warnings;
    if (!FTrafficRenderManifestLoader::LoadRenderRunManifest(ManifestPath, Manifest, Geometry, Warnings, OutError))
    {
        QaSummary.Warnings = MoveTemp(Warnings);
        QaSummary.ParseErrorCount = Trace.ParseErrorCount;
        return false;
    }
    if (!Trace.LoadJsonLines(Manifest.VehicleTracePath, MaxFrames, OutError))
    {
        QaSummary.Warnings = MoveTemp(Warnings);
        QaSummary.ParseErrorCount = Trace.ParseErrorCount;
        return false;
    }
    Warnings.Append(Trace.Warnings);
    CoordinateTransform = FSumoCoordinateTransform(Geometry.LocalOriginMeters);
    Clock.Configure(Trace.StartTimeSeconds(), Trace.EndTimeSeconds());
    QaSummary.bManifestLoaded = true;
    QaSummary.RunId = Manifest.RunId;
    QaSummary.TraceSchemaVersion = Trace.Frames[0].SchemaVersion;
    QaSummary.LoadedFrameCount = Trace.Frames.Num();
    QaSummary.UniqueVehicleCount = Trace.UniqueVehicleIds.Num();
    QaSummary.LocalOriginMeters = Geometry.LocalOriginMeters;
    QaSummary.Warnings = MoveTemp(Warnings);
    RefreshCurrentFrame();
    return true;
}

void UTrafficReplaySubsystem::Play() { Clock.Play(); }
void UTrafficReplaySubsystem::Pause() { Clock.Pause(); }
void UTrafficReplaySubsystem::Seek(const double TimeSeconds) { Clock.Seek(TimeSeconds); RefreshCurrentFrame(); }
void UTrafficReplaySubsystem::AdvanceReplay(const double DeltaSeconds) { Clock.Advance(DeltaSeconds); RefreshCurrentFrame(); }
bool UTrafficReplaySubsystem::IsPlaying() const { return Clock.bPlaying; }
double UTrafficReplaySubsystem::GetCurrentTimeSeconds() const { return Clock.CurrentTimeSeconds; }
FTrafficVehicleTraceFrame UTrafficReplaySubsystem::GetCurrentFrame() const { return CurrentFrame; }
FTrafficReplayQaSummary UTrafficReplaySubsystem::GetQaSummary() const { return QaSummary; }

bool UTrafficReplaySubsystem::WriteQualityReport(const FString& OutputPath, FString& OutError) const
{
    if (OutputPath.IsEmpty() || !FFileHelper::SaveStringToFile(QaSummary.ToJson(), *OutputPath))
    {
        OutError = FString::Printf(TEXT("Unable to write Unreal render QA report: %s"), *OutputPath);
        return false;
    }
    return true;
}

void UTrafficReplaySubsystem::RecordAppliedFrame(const int32 ActiveVehicleCount, const int32 DroppedVehicleCount)
{
    ++QaSummary.FramesApplied;
    QaSummary.LargestActiveVehicleCount = FMath::Max(QaSummary.LargestActiveVehicleCount, ActiveVehicleCount);
    QaSummary.DroppedDebugVehicleCount += DroppedVehicleCount;
    QaSummary.bSuccess = QaSummary.bManifestLoaded && QaSummary.ParseErrorCount == 0;
}

void UTrafficReplaySubsystem::RefreshCurrentFrame()
{
    Trace.Sample(Clock.CurrentTimeSeconds, CurrentFrame);
}
