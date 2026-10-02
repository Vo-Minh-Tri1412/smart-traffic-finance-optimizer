#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "TrafficRenderBridgeLibrary.generated.h"

UCLASS()
class TRAFFICRENDERRUNTIME_API UTrafficRenderBridgeLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    static FString ValidateRenderRunManifest(const FString& ManifestPath);

    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    static FString ValidateVehicleTrace(const FString& TracePath, int32 MaxFrames = 0);

    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    static FString ValidateCameraCalibration(const FString& CalibrationPath);

    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    static FString RunContractSelfTest();

    UFUNCTION(BlueprintPure, Category = "Traffic Render")
    static FTransform ComputeVehicleCuboidTransform(
        double X,
        double Y,
        double ElevationM,
        double AngleDegrees,
        double LengthM,
        double WidthM,
        double HeightM,
        double GroundClearanceM,
        FVector2D LocalOriginMeters);
};
