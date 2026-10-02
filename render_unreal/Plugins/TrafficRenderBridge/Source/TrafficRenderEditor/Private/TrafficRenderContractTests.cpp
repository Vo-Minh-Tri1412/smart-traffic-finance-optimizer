#include "Misc/AutomationTest.h"

#include "TrafficRenderBridgeLibrary.h"
#include "TrafficCityAssetCatalog.h"
#include "TrafficCityVisualActor.h"
#include "SumoCoordinateTransform.h"
#include "TrafficVehicleTrace.h"
#include "TrafficRenderManifest.h"
#include "TrafficSumoGeometryActor.h"
#include "ProceduralMeshComponent.h"
#include "Engine/StaticMesh.h"
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
    TestEqual(TEXT("fixture geometry occupies one cullable road tile"), Roads->RenderedTileCount, 1);
    TArray<UProceduralMeshComponent*> RoadComponents;
    Roads->GetComponents<UProceduralMeshComponent>(RoadComponents);
    UProceduralMeshComponent* Tile = nullptr;
    for (UProceduralMeshComponent* Component : RoadComponents)
    {
        if (Component && Component->GetNumSections() > 0) Tile = Component;
    }
    if (TestNotNull(TEXT("fixture road tile mesh"), Tile))
    {
        const FProcMeshSection* Section = Tile->GetProcMeshSection(0);
        if (TestNotNull(TEXT("fixture road tile section"), Section) && Section->ProcVertexBuffer.Num() >= 8)
        {
            TestTrue(TEXT("first segment starts at U=0"), FMath::IsNearlyZero(Section->ProcVertexBuffer[0].UV0.X));
            TestTrue(TEXT("first 20m segment ends at U=10"), FMath::IsNearlyEqual(Section->ProcVertexBuffer[1].UV0.X, 10.0f));
            TestTrue(TEXT("second segment continues at U=10"), FMath::IsNearlyEqual(Section->ProcVertexBuffer[4].UV0.X, 10.0f));
            TestTrue(TEXT("second segment ends at U=20"), FMath::IsNearlyEqual(Section->ProcVertexBuffer[5].UV0.X, 20.0f));
            TestTrue(TEXT("3.2m lane width maps to V=1.6"), FMath::IsNearlyEqual(Section->ProcVertexBuffer[2].UV0.Y, 1.6f));
        }
    }
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
    TestTrue(TEXT("prepared network is divided into multiple road tiles"), Roads->RenderedTileCount > 1);
    const FString ReportDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"));
    IFileManager::Get().MakeDirectory(*ReportDirectory, true);
    const FString Report = FPaths::Combine(ReportDirectory, TEXT("prepared_run_geometry.json"));
    TestTrue(TEXT("geometry QA report written"), FFileHelper::SaveStringToFile(Roads->GetBuildSummaryJson(), *Report));
    AddInfo(FString::Printf(TEXT("Prepared run %s: %d frames loaded, %d lanes built; QA %s"),
        *Manifest.RunId, Trace.Frames.Num(), Roads->RenderedLaneCount, *Report));
    Roads->Destroy();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FTrafficCityVisualPlacementTest,
    "TrafficRender.Bridge.CityVisualPlacement",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FTrafficCityVisualPlacementTest::RunTest(const FString& Parameters)
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!TestNotNull(TEXT("editor world"), World)) return false;
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!TestNotNull(TEXT("engine cube fixture mesh"), Cube)) return false;
    UTrafficCityAssetCatalog* Catalog = NewObject<UTrafficCityAssetCatalog>(World);
    if (!TestNotNull(TEXT("visual catalog"), Catalog)) return false;
    FTrafficCityVisualStyle Building;
    Building.ZoneType = TEXT("residential");
    Building.Kind = TEXT("building");
    Building.Mesh = Cube;
    Building.AssetSource = TEXT("Unreal Engine fixture mesh");
    Building.License = TEXT("engine fixture only");
    Catalog->Styles.Add(Building);
    FTrafficCityVisualStyle Landscape = Building;
    Landscape.ZoneType = TEXT("neutral");
    Landscape.Kind = TEXT("landscape");
    Catalog->Styles.Add(Landscape);
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    ATrafficCityVisualActor* City = World->SpawnActor<ATrafficCityVisualActor>(Spawn);
    if (!TestNotNull(TEXT("city visual actor"), City)) return false;
    City->AssetCatalog = Catalog;
    City->ExpectedNetSha256 = TEXT("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    City->ExpectedOverlaySha256 = TEXT("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
    FString Error;
    const FString Path = FPaths::Combine(FPaths::ProjectDir(), TEXT("Tests/Fixtures/city_visual/placements.json"));
    const bool bBuilt = City->BuildFromPlacementManifest(Path, Error);
    TestTrue(TEXT("visual placements load with matching map hashes"), bBuilt);
    if (!bBuilt) AddError(Error);
    TestEqual(TEXT("one building instance"), City->RenderedBuildingCount, 1);
    TestEqual(TEXT("one landscape instance"), City->RenderedLandscapeCount, 1);
    TestEqual(TEXT("two instanced visual styles"), City->RenderedStyleCount, 2);
    City->Destroy();
    return true;
}
