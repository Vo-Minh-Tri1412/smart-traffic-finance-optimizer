#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TrafficSumoGeometryActor.generated.h"

class UProceduralMeshComponent;
class UMaterialInterface;

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API ATrafficSumoGeometryActor : public AActor
{
    GENERATED_BODY()

public:
    ATrafficSumoGeometryActor();

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Traffic Render")
    bool BuildFromGeometryManifest(const FString& InGeometryManifestPath, int32 MaxLanes, FString& OutError);

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Traffic Render")
    bool RebuildConfiguredGeometry(FString& OutError);

    UFUNCTION(BlueprintPure, Category = "Traffic Render") FString GetBuildSummaryJson() const;

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 TotalLaneCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 RenderedLaneCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 RenderedSegmentCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 SkippedDegenerateSegmentCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 JunctionCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") int32 RenderedTileCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render") FVector2D LocalOriginMeters = FVector2D::ZeroVector;

    // Project-relative paths can be used here to keep generated levels relocatable.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|Road Geometry")
    FString GeometryManifestPath;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|Road Geometry", meta = (ClampMin = "0"))
    int32 PreviewMaxLanes = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|Road Appearance")
    TObjectPtr<UMaterialInterface> RoadMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|Road Geometry", meta = (ClampMin = "100.0"))
    float TileSizeMeters = 500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|Road Appearance", meta = (ClampMin = "0.1"))
    float TextureRepeatMeters = 2.0f;

private:
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render") TObjectPtr<UProceduralMeshComponent> RoadMesh;
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render") TArray<TObjectPtr<UProceduralMeshComponent>> TileMeshes;
};
