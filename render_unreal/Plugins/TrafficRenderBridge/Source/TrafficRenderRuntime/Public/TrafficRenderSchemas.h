#pragma once

#include "CoreMinimal.h"

namespace TrafficRenderSchemas
{
    inline constexpr TCHAR GeometryManifest[] = TEXT("geometry_manifest.v1");
    inline constexpr TCHAR VehicleTrace[] = TEXT("vehicle_trace.v2");
    inline constexpr TCHAR VisibilityTrace[] = TEXT("visibility_trace.v1");
    inline constexpr TCHAR TrafficLightTrace[] = TEXT("traffic_light_trace.v1");
    inline constexpr TCHAR SemanticOverlay[] = TEXT("semantic_overlay.v2");
    inline constexpr TCHAR EventTrace[] = TEXT("event_trace.v1");
    inline constexpr TCHAR RenderRunManifest[] = TEXT("render_run_manifest.v1");
    inline constexpr TCHAR SensorDatasetManifest[] = TEXT("sensor_dataset_manifest.v1");
    inline constexpr TCHAR CameraCalibration[] = TEXT("camera_calibration.v1");

    inline constexpr TCHAR SumoCoordinateSystem[] = TEXT("sumo_xy_meters");
    inline constexpr TCHAR FrontBumperReferencePoint[] = TEXT("front_bumper_center");
    inline constexpr double UnrealCentimetersPerMeter = 100.0;

    TRAFFICRENDERRUNTIME_API TMap<FString, FString> GetRenderBridgeVersions();
}
