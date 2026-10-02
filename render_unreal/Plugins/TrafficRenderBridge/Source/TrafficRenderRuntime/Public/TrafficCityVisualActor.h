#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TrafficCityVisualActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UTrafficCityAssetCatalog;

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API ATrafficCityVisualActor : public AActor
{
    GENERATED_BODY()

public:
    ATrafficCityVisualActor();

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Traffic Render|City Visual")
    bool BuildFromPlacementManifest(const FString& InManifestPath, FString& OutError);

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Traffic Render|City Visual")
    bool RebuildConfiguredPlacements(FString& OutError);

    UFUNCTION(BlueprintPure, Category = "Traffic Render|City Visual")
    FString GetBuildSummaryJson() const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|City Visual")
    TObjectPtr<UTrafficCityAssetCatalog> AssetCatalog;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|City Visual")
    FString PlacementManifestPath;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|City Visual")
    FString ExpectedNetSha256;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render|City Visual")
    FString ExpectedOverlaySha256;

    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render|City Visual") int32 RenderedBuildingCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render|City Visual") int32 RenderedLandscapeCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render|City Visual") int32 RenderedStyleCount = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Traffic Render|City Visual") FVector2D LocalOriginMeters = FVector2D::ZeroVector;

private:
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render|City Visual") TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY(VisibleAnywhere, Category = "Traffic Render|City Visual")
    TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> StyleComponents;
};
