#pragma once

#include "CoreMinimal.h"
#include "TrafficRenderTypes.h"

struct TRAFFICRENDERRUNTIME_API FSumoCoordinateTransform
{
    FVector2D LocalOriginMeters = FVector2D::ZeroVector;

    explicit FSumoCoordinateTransform(const FVector2D& InLocalOriginMeters = FVector2D::ZeroVector)
        : LocalOriginMeters(InLocalOriginMeters)
    {
    }

    FVector SumoPointToUnreal(double X, double Y, double ZMeters = 0.0) const;
    FVector UnrealPointToSumo(const FVector& UnrealPoint) const;
    double SumoAngleToUnrealYaw(double SumoAngleDegrees) const;
    FTransform VehicleCuboidTransform(const FTrafficVehicleState& Vehicle) const;
};
