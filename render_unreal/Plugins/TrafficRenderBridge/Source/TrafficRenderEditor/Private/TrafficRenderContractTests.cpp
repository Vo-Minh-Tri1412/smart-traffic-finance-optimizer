#include "Misc/AutomationTest.h"

#include "TrafficRenderBridgeLibrary.h"
#include "SumoCoordinateTransform.h"
#include "TrafficVehicleTrace.h"
#include "TrafficRenderManifest.h"
#include "TrafficSumoGeometryActor.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "Misc/Parse.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FTrafficRenderContractSelfTest,
    "TrafficRender.Bridge.ContractSelfTest",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FTrafficRenderContractSelfTest::RunTest(const FString& Parameters)
{
    const FString Result = UTrafficRenderBridgeLibrary::RunContractSelfTest();
    TestTrue(TEXT("schema registry and front-bumper coordinate self-test"), Result.Contains(TEXT("\"success\":true")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FTrafficRenderReplayTest,
    "TrafficRender.Bridge.ReplayInterpolation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FTrafficRenderReplayTest::RunTest(const FString& Parameters)
{
    FTrafficVehicleTrace Trace;
    FTrafficVehicleTraceFrame Left, Right, Sample;
    Left.TimeSeconds = 0.0;
    Right.TimeSeconds = 2.0;
    FTrafficVehicleState Vehicle;
    Vehicle.VehicleId = TEXT("v1");
    Vehicle.AngleDegrees = 350.0;
    Left.Vehicles.Add(Vehicle);
    Vehicle.X = 10.0;
    Vehicle.AngleDegrees = 10.0;
    Right.Vehicles.Add(Vehicle);
    Trace.Frames.Add(Left);
    Trace.Frames.Add(Right);
    TestTrue(TEXT("midpoint is available"), Trace.Sample(1.0, Sample));
    TestEqual(TEXT("linear trajectory midpoint"), Sample.Vehicles[0].X, 5.0);
    TestTrue(TEXT("heading follows shortest arc across north"),
        FMath::IsNearlyZero(FMath::UnwindDegrees(Sample.Vehicles[0].AngleDegrees)));
    const FSumoCoordinateTransform Transform(FVector2D(100.0, 200.0));
    const FVector Original(102.5, 203.75, 4.0);
    TestTrue(TEXT("coordinate round trip"), Transform.UnrealPointToSumo(
        Transform.SumoPointToUnreal(Original.X, Original.Y, Original.Z)).Equals(Original, 1.e-6));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FTrafficRenderArtifactTest,
    "TrafficRender.Bridge.ArtifactReplay",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FTrafficRenderArtifactTest::RunTest(const FString& Parameters)
{
    const FString Path = FPaths::Combine(FPaths::ProjectDir(), TEXT("Tests/Fixtures/replay_contract/manifest.json"));
    FTrafficRenderRunManifest Manifest;
    FTrafficGeometryManifest Geometry;
    TArray<FString> Warnings;
    FString Error;
    if (!TestTrue(TEXT("load manifest and relative geometry"),
        FTrafficRenderManifestLoader::LoadRenderRunManifest(Path, Manifest, Geometry, Warnings, Error)))
    {
        AddError(Error);
        return false;
    }
    FTrafficVehicleTrace Trace;
    if (!TestTrue(TEXT("load JSONL trace"), Trace.LoadJsonLines(Manifest.VehicleTracePath, 0, Error)))
    {
        AddError(Error);
        return false;
    }
    TestEqual(TEXT("fixture frame count"), Trace.Frames.Num(), 2);
    TestEqual(TEXT("unique vehicle count"), Trace.UniqueVehicleIds.Num(), 1);
    FTrafficVehicleTraceFrame Frame;
    if (!TestTrue(TEXT("sample fixture midpoint"), Trace.Sample(1.0, Frame)) || Frame.Vehicles.Num() != 1)
        return false;
    TestEqual(TEXT("fixture midpoint in SUMO metres"), Frame.Vehicles[0].X, 115.0);
    const FTransform Pose = FSumoCoordinateTransform(Geometry.LocalOriginMeters).VehicleCuboidTransform(Frame.Vehicles[0]);
    TestTrue(TEXT("front bumper offset and cm scale"), Pose.GetLocation().Equals(FVector(1300.0, 200.0, 85.0), 0.01));

    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!TestNotNull(TEXT("editor world"), World)) return false;
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    ATrafficSumoGeometryActor* Roads = World->SpawnActor<ATrafficSumoGeometryActor>(Spawn);
    if (!TestNotNull(TEXT("geometry actor"), Roads)) return false;
    const bool bBuilt = Roads->BuildFromGeometryManifest(Manifest.GeometryManifestPath, 0, Error);
    TestTrue(TEXT("native SUMO lane mesh build"), bBuilt);
    if (!bBuilt) AddError(Error);
    TestEqual(TEXT("native rendered lane count"), Roads->RenderedLaneCount, 1);
    TestEqual(TEXT("native segment count"), Roads->RenderedSegmentCount, 2);
    TestEqual(TEXT("native junction count"), Roads->JunctionCount, 2);
    Roads->Destroy();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FTrafficRenderPreparedRunTest,
    "TrafficRender.Bridge.PreparedRun",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FTrafficRenderPreparedRunTest::RunTest(const FString& Parameters)
{
    FString Path;
    if (!FParse::Value(FCommandLine::Get(), TEXT("TrafficRenderManifest="), Path))
    {
        AddInfo(TEXT("Prepared map check not requested; supply -TrafficRenderManifest=<absolute manifest path>"));
        return true;
    }
    FTrafficRenderRunManifest Manifest;
    FTrafficGeometryManifest Geometry;
    TArray<FString> Warnings;
    FString Error;
    if (!FTrafficRenderManifestLoader::LoadRenderRunManifest(Path, Manifest, Geometry, Warnings, Error))
    {
        AddError(Error);
        return false;
    }
    FTrafficVehicleTrace Trace;
    if (!Trace.LoadJsonLines(Manifest.VehicleTracePath, 3, Error))
    {
        AddError(Error);
        return false;
    }
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!TestNotNull(TEXT("editor world"), World)) return false;
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    ATrafficSumoGeometryActor* Roads = World->SpawnActor<ATrafficSumoGeometryActor>(Spawn);
    if (!TestNotNull(TEXT("geometry actor"), Roads)) return false;
    const bool bBuilt = Roads->BuildFromGeometryManifest(Manifest.GeometryManifestPath, 0, Error);
    TestTrue(TEXT("all prepared network lane geometry loads"), bBuilt);
    if (!bBuilt) AddError(Error);
    TestTrue(TEXT("prepared network contains lane geometry"), Roads->RenderedLaneCount > 0);
    const FString ReportDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"));
    IFileManager::Get().MakeDirectory(*ReportDirectory, true);
    const FString Report = FPaths::Combine(ReportDirectory, TEXT("prepared_run_geometry.json"));
    TestTrue(TEXT("geometry QA report written"), FFileHelper::SaveStringToFile(Roads->GetBuildSummaryJson(), *Report));
    AddInfo(FString::Printf(TEXT("Prepared run %s: %d frames loaded, %d lanes built; QA %s"),
        *Manifest.RunId, Trace.Frames.Num(), Roads->RenderedLaneCount, *Report));
    Roads->Destroy();
    return true;
}
