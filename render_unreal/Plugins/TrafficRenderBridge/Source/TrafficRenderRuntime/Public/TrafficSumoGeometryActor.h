#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TrafficSumoGeometryActor.generated.h"

class UProceduralMeshComponent;

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API ATrafficSumoGeometryActor : public AActor
{
    GENERATED_BODY()

public:
    ATrafficSumoGeometryActor();

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Traffic Render")
    bool BuildFromGeometryManifest(const FString& GeometryManifestPath, int32 MaxLanes, FString& OutError);

    UFUNCTION(BlueprintPure, Category = "Traffic Render") FString GetBuildSummaryJson() const;

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 TotalLaneCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 RenderedLaneCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 RenderedSegmentCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 JunctionCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector2D LocalOriginMeters = FVector2D::ZeroVector;

private:
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render") TObjectPtr<UProceduralMeshComponent> RoadMesh;
};
