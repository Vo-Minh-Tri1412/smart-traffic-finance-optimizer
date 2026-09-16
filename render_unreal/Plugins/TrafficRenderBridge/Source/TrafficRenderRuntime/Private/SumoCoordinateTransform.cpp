#include "SumoCoordinateTransform.h"
#include "TrafficRenderSchemas.h"

#include "Math/UnrealMathUtility.h"

FVector FSumoCoordinateTransform::SumoPointToUnreal(const double X, const double Y, const double ZMeters) const
{
    // SUMO uses metres and an explicit local origin; Unreal uses centimetres.
    return FVector(
        (X - LocalOriginMeters.X) * TrafficRenderSchemas::UnrealCentimetersPerMeter,
        (Y - LocalOriginMeters.Y) * TrafficRenderSchemas::UnrealCentimetersPerMeter,
        ZMeters * TrafficRenderSchemas::UnrealCentimetersPerMeter);
}

FVector FSumoCoordinateTransform::UnrealPointToSumo(const FVector& UnrealPoint) const
{
    return FVector(
        UnrealPoint.X / TrafficRenderSchemas::UnrealCentimetersPerMeter + LocalOriginMeters.X,
        UnrealPoint.Y / TrafficRenderSchemas::UnrealCentimetersPerMeter + LocalOriginMeters.Y,
        UnrealPoint.Z / TrafficRenderSchemas::UnrealCentimetersPerMeter);
}

double FSumoCoordinateTransform::SumoAngleToUnrealYaw(const double SumoAngleDegrees) const
{
    // SUMO 0° points north (+Y); Unreal yaw 0° points +X.
    return FMath::UnwindDegrees(90.0 - SumoAngleDegrees);
}

FTransform FSumoCoordinateTransform::VehicleCuboidTransform(const FTrafficVehicleState& Vehicle) const
{
    const double AngleRadians = FMath::DegreesToRadians(Vehicle.AngleDegrees);
    const FVector2D Forward(static_cast<float>(FMath::Sin(AngleRadians)), static_cast<float>(FMath::Cos(AngleRadians)));
    const double CenterX = Vehicle.X - static_cast<double>(Forward.X) * Vehicle.LengthM * 0.5;
    const double CenterY = Vehicle.Y - static_cast<double>(Forward.Y) * Vehicle.LengthM * 0.5;
    const double CenterZ = Vehicle.ElevationM + Vehicle.GroundClearanceM + Vehicle.HeightM * 0.5;

    return FTransform(
        FRotator(0.0, SumoAngleToUnrealYaw(Vehicle.AngleDegrees), 0.0),
        SumoPointToUnreal(CenterX, CenterY, CenterZ),
        FVector(Vehicle.LengthM, Vehicle.WidthM, Vehicle.HeightM));
}
