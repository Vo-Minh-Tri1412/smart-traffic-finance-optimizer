#pragma once

#include "CoreMinimal.h"
#include "TrafficRenderTypes.h"

/** Loader for the renderer-neutral camera_calibration.v1 artifact. */
class TRAFFICRENDERRUNTIME_API FTrafficCameraCalibrationLoader
{
public:
    static bool Load(
        const FString& Path,
        TArray<FTrafficCameraCalibration>& OutCameras,
        TArray<FString>& OutWarnings,
        FString& OutError);
};
