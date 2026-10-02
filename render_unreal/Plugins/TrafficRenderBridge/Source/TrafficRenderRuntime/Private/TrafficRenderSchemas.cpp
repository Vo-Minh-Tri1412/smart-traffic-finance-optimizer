#include "TrafficRenderSchemas.h"

TMap<FString, FString> TrafficRenderSchemas::GetRenderBridgeVersions()
{
    return {
        {TEXT("geometry_manifest"), GeometryManifest},
        {TEXT("vehicle_trace"), VehicleTrace},
        {TEXT("visibility_trace"), VisibilityTrace},
        {TEXT("traffic_light_trace"), TrafficLightTrace},
        {TEXT("semantic_overlay"), SemanticOverlay},
        {TEXT("event_trace"), EventTrace},
        {TEXT("render_run_manifest"), RenderRunManifest},
        {TEXT("sensor_dataset_manifest"), SensorDatasetManifest},
        {TEXT("camera_calibration"), CameraCalibration},
    };
}
