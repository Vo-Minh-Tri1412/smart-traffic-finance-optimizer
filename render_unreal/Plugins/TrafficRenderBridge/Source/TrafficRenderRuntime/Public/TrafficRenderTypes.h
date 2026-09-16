#pragma once

#include "CoreMinimal.h"
#include "TrafficRenderTypes.generated.h"

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficGeometryManifest
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString SchemaVersion;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString GeometrySource;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString NetXmlPath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString CoordinateSystem;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector2D BoundsMin = FVector2D::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector2D BoundsMax = FVector2D::ZeroVector;
    /** Explicit SUMO-meter origin used by every replay/render adapter. */
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector2D LocalOriginMeters = FVector2D::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 LaneCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 JunctionCount = 0;
};

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficCameraCalibration
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString SchemaVersion;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString CameraId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString Role;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString CoordinateSystem;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector PositionMeters = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FRotator RotationDegrees = FRotator::ZeroRotator;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FIntPoint ImageSize = FIntPoint::ZeroValue;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FIntPoint GeometryRasterSize = FIntPoint::ZeroValue;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double Fx = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double Fy = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double Cx = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double Cy = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double NearClipMeters = 0.1;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double FarClipMeters = 500.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double CaptureIntervalSeconds = 1.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") TArray<FString> TargetLaneIds;
};

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficRenderRunManifest
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString SchemaVersion;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString RunId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString ManifestPath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString GeometryManifestPath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleTracePath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString TrafficLightTracePath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString SemanticOverlayPath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString EventTracePath;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString Renderer;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString QualityReportPath;
};

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficVehicleState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleType;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double X = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double Y = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double Speed = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double AngleDegrees = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString LaneId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString RoadId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double LengthM = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double WidthM = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double HeightM = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double GroundClearanceM = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double ElevationM = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double PosLatM = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double LateralSpeedMps = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double AccelerationMps2 = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString ElevationSource;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString ReferencePoint;
};

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficVehicleTraceFrame
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString SchemaVersion;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int64 Timestep = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") double TimeSeconds = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString DistrictId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString ScenarioId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString ControllerId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString EngineId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") TArray<FTrafficVehicleState> Vehicles;
};

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficReplayQaSummary
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") bool bSuccess = false;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") bool bManifestLoaded = false;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString RunId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString TraceSchemaVersion;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 LoadedFrameCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 FramesApplied = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 UniqueVehicleCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 LargestActiveVehicleCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 DroppedDebugVehicleCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 ParseErrorCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector2D LocalOriginMeters = FVector2D::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") TArray<FString> Warnings;

    FString ToJson() const;
};
