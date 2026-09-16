#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TrafficRenderTypes.h"
#include "TrafficReplayVehicleActor.generated.h"

class UStaticMeshComponent;

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API ATrafficReplayVehicleActor : public AActor
{
    GENERATED_BODY()

public:
    ATrafficReplayVehicleActor();

    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    void ApplyVehicleState(const FTrafficVehicleState& State, const FTransform& CuboidTransform);

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleType;

private:
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render") TObjectPtr<UStaticMeshComponent> VehicleMesh;
};
