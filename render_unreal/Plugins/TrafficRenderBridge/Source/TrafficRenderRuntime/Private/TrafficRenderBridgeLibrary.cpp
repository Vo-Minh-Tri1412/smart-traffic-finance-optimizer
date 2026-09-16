#include "TrafficRenderBridgeLibrary.h"

#include "TrafficCameraCalibration.h"
#include "TrafficRenderManifest.h"
#include "TrafficRenderSchemas.h"
#include "TrafficVehicleTrace.h"
#include "SumoCoordinateTransform.h"

namespace
{
    FString ResultJson(const bool bSuccess, const FString& Error, const TArray<FString>& Warnings, const int32 Count = 0)
    {
        FString Json = FString::Printf(TEXT("{\"success\":%s,\"count\":%d,\"error\":\"%s\",\"warnings\":["),
            bSuccess ? TEXT("true") : TEXT("false"), Count, *Error.ReplaceCharWithEscapedChar());
        for (int32 Index = 0; Index < Warnings.Num(); ++Index)
        {
            if (Index > 0) Json += TEXT(",");
            Json += FString::Printf(TEXT("\"%s\""), *Warnings[Index].ReplaceCharWithEscapedChar());
        }
        Json += TEXT("]}\n");
        return Json;
    }
}

FString UTrafficRenderBridgeLibrary::ValidateRenderRunManifest(const FString& ManifestPath)
{
    FTrafficRenderRunManifest Manifest;
    FTrafficGeometryManifest Geometry;
    TArray<FString> Warnings;
    FString Error;
    const bool bSuccess = FTrafficRenderManifestLoader::LoadRenderRunManifest(ManifestPath, Manifest, Geometry, Warnings, Error);
    return ResultJson(bSuccess, Error, Warnings, bSuccess ? 1 : 0);
}

FString UTrafficRenderBridgeLibrary::ValidateVehicleTrace(const FString& TracePath, const int32 MaxFrames)
{
    FTrafficVehicleTrace Trace;
    FString Error;
    const bool bSuccess = Trace.LoadJsonLines(TracePath, MaxFrames, Error);
    return ResultJson(bSuccess, Error, Trace.Warnings, Trace.Frames.Num());
}

FString UTrafficRenderBridgeLibrary::ValidateCameraCalibration(const FString& CalibrationPath)
{
    TArray<FTrafficCameraCalibration> Cameras;
    TArray<FString> Warnings;
    FString Error;
    const bool bSuccess = FTrafficCameraCalibrationLoader::Load(CalibrationPath, Cameras, Warnings, Error);
    return ResultJson(bSuccess, Error, Warnings, Cameras.Num());
}

FString UTrafficRenderBridgeLibrary::RunContractSelfTest()
{
    const TMap<FString, FString> Versions = TrafficRenderSchemas::GetRenderBridgeVersions();
    const bool bVersions = Versions.Num() == 9 && Versions.FindRef(TEXT("vehicle_trace")) == TrafficRenderSchemas::VehicleTrace &&
        Versions.FindRef(TEXT("camera_calibration")) == TrafficRenderSchemas::CameraCalibration;
    FTrafficVehicleState Vehicle;
    Vehicle.X = 100.0;
    Vehicle.Y = 200.0;
    Vehicle.AngleDegrees = 0.0;
    Vehicle.LengthM = 4.0;
    Vehicle.WidthM = 2.0;
    Vehicle.HeightM = 1.5;
    Vehicle.GroundClearanceM = 0.1;
    const FTransform Transform = FSumoCoordinateTransform(FVector2D(100.0, 100.0)).VehicleCuboidTransform(Vehicle);
    const bool bTransform = FMath::IsNearlyEqual(Transform.GetLocation().X, 0.0, 0.01) &&
        FMath::IsNearlyEqual(Transform.GetLocation().Y, 9800.0, 0.01) &&
        FMath::IsNearlyEqual(Transform.GetLocation().Z, 85.0, 0.01);
    TArray<FString> Warnings;
    if (!bVersions) Warnings.Add(TEXT("schema version registry is incomplete"));
    if (!bTransform) Warnings.Add(TEXT("front-bumper-to-center coordinate transform failed"));
    return ResultJson(bVersions && bTransform, TEXT(""), Warnings, bVersions && bTransform ? 1 : 0);
}

FTransform UTrafficRenderBridgeLibrary::ComputeVehicleCuboidTransform(
    const double X, const double Y, const double ElevationM, const double AngleDegrees,
    const double LengthM, const double WidthM, const double HeightM, const double GroundClearanceM,
    const FVector2D LocalOriginMeters)
{
    FTrafficVehicleState Vehicle;
    Vehicle.X = X; Vehicle.Y = Y; Vehicle.ElevationM = ElevationM; Vehicle.AngleDegrees = AngleDegrees;
    Vehicle.LengthM = LengthM; Vehicle.WidthM = WidthM; Vehicle.HeightM = HeightM; Vehicle.GroundClearanceM = GroundClearanceM;
    return FSumoCoordinateTransform(LocalOriginMeters).VehicleCuboidTransform(Vehicle);
}
