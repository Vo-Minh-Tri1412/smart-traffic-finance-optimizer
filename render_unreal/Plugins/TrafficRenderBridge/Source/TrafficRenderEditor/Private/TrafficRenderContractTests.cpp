#include "Misc/AutomationTest.h"

#include "TrafficRenderBridgeLibrary.h"
#include "SumoCoordinateTransform.h"
#include "TrafficVehicleTrace.h"

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
