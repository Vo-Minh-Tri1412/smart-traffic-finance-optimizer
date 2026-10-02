#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "TrafficCityAssetCatalog.generated.h"

class UMaterialInterface;
class UStaticMesh;

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficCityVisualStyle
{
    GENERATED_BODY()

    // Matches the semantic overlay category; the artist can replace assets without changing SUMO.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual") FName ZoneType;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual") FName Kind;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual") TSoftObjectPtr<UStaticMesh> Mesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual") TSoftObjectPtr<UMaterialInterface> MaterialOverride;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual", meta = (ClampMin = "0.1"))
    float MaxFootprintDiameterMeters = 20.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual", meta = (ClampMin = "0.1"))
    float MinHeightMeters = 8.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual", meta = (ClampMin = "0.1"))
    float MaxHeightMeters = 20.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual", meta = (ClampMin = "1.0"))
    float EndCullDistanceMeters = 20000.0f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual") FString AssetSource;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual") FString License;
};

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficCityAssetCatalog : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "City Visual")
    TArray<FTrafficCityVisualStyle> Styles;
};
