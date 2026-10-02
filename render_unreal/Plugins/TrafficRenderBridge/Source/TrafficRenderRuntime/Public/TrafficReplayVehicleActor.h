#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TrafficRenderTypes.h"
#include "TrafficLiveProfile.h"
#include "TrafficReplayVehicleActor.generated.h"

class UStaticMeshComponent;
class USceneComponent;

UCLASS(BlueprintType, Blueprintable)
class TRAFFICRENDERRUNTIME_API ATrafficReplayVehicleActor : public AActor
{
    GENERATED_BODY()

public:
    ATrafficReplayVehicleActor();

    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    void ApplyVehicleState(const FTrafficVehicleState& State, const FTransform& CuboidTransform);
    bool ConfigureVisual(const FTrafficVehicleVisualDefinition& Definition, FString& OutError);
    UFUNCTION(BlueprintImplementableEvent, Category="Traffic Render")
    void OnSimulationStateApplied(const FTrafficVehicleState& State);
    FVector GetVisualDimensionsMeters() const;
    FVector GetTemplateDimensionsMeters() const { return VisualBounds.GetSize() / 100; }

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleId;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FString VehicleType;

private:
    UPROPERTY(VisibleAnywhere, Category="Traffic Render") TObjectPtr<USceneComponent> CanonicalRoot;
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render") TObjectPtr<UStaticMeshComponent> VehicleMesh;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> VisualParts;
    FBox VisualBounds = FBox(ForceInit);
    FRotator VisualOrientation = FRotator::ZeroRotator;
    bool bPreserveAspectRatio = true;
    void FitVisual(const FVector& CanonicalSizeCm);
};
