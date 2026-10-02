#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Actor.h"
#include "TrafficUrbanEnvironment.generated.h"

class UMaterialInterface;
class UStaticMesh;
class UProceduralMeshComponent;
class UHierarchicalInstancedStaticMeshComponent;

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficBuildingHeightRule
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Height") FString BuildingTag = TEXT("*");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Height", meta=(ClampMin="1")) float MinHeightMeters = 6;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Height", meta=(ClampMin="1")) float MaxHeightMeters = 15;
};

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficUrbanAssetCatalog : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings", meta=(AssetBundles="Live")) TArray<TSoftObjectPtr<UMaterialInterface>> FacadeMaterials;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> RoofMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> WhiteMarkingMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> YellowMarkingMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> SidewalkMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> CurbMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(AssetBundles="Live")) TArray<TSoftObjectPtr<UStaticMesh>> TreeMeshParts;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> TreeMaterialOverride;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Provenance") FString TreeSource;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Provenance") FString TreeLicense;
};

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficUrbanPlacementProfile : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Source") FString GeometrySourcePath;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Source") FString GeometrySourceSha256;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Source") FString GeometrySourceSha1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Source") FString ExpectedNetSha256;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings") TArray<FTrafficBuildingHeightRule> HeightRules;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings") TMap<FString,float> BuildingHeightOverrides;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings") int32 HeightSeed = 109;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings", meta=(ClampMin="1")) float FloorHeightMeters = 3;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings", meta=(ClampMin="1")) float WindowModuleWidthMeters = 3;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Buildings") FString HeightAssumption = TEXT("Synthetic visual height; not surveyed.");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(ClampMin="0.05")) float MarkingWidthMeters = 0.12f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(ClampMin="0.1")) float DashLengthMeters = 3;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(ClampMin="0.1")) float DashGapMeters = 5;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(ClampMin="0")) float SidewalkWidthMeters = 1.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(ClampMin="0")) float SidewalkHeightMeters = 0.12f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Street", meta=(ClampMin="0")) float JunctionSetbackMeters = 6;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(ClampMin="3")) float TreeSpacingMeters = 18;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(ClampMin="1")) float TreeHeightMeters = 5;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(ClampMin="0")) float TreeSetbackMeters = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(ClampMin="0")) float TreeCrownRadiusMeters = 1.25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Greenery", meta=(ClampMin="10")) float TreeCullDistanceMeters = 250;
};

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficUrbanSceneProfile : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Profiles", meta=(AssetBundles="Live")) TSoftObjectPtr<UTrafficUrbanAssetCatalog> Catalog;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Profiles", meta=(AssetBundles="Live")) TSoftObjectPtr<UTrafficUrbanPlacementProfile> Placement;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Rendering", meta=(ClampMin="100")) float TileSizeMeters = 400;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Rendering") bool Buildings = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Rendering") bool Markings = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Rendering") bool Sidewalks = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Rendering") bool Greenery = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Rendering") bool CastShadows = false;
};

UCLASS(BlueprintType, Blueprintable)
class TRAFFICRENDERRUNTIME_API ATrafficUrbanEnvironment : public AActor
{
    GENERATED_BODY()
public:
    ATrafficUrbanEnvironment();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Urban Environment") TObjectPtr<UTrafficUrbanSceneProfile> Profile;
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Urban Environment") bool Rebuild(FString& OutError);
    UFUNCTION(BlueprintPure, Category="Urban Environment") FString GetSummaryJson() const;
    UPROPERTY(BlueprintReadOnly, Category="Urban Environment") int32 BuildingParts = 0;
    UPROPERTY(BlueprintReadOnly, Category="Urban Environment") int32 MarkingSegments = 0;
    UPROPERTY(BlueprintReadOnly, Category="Urban Environment") int32 SidewalkSegments = 0;
    UPROPERTY(BlueprintReadOnly, Category="Urban Environment") int32 TreeCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Urban Environment") int32 RejectedTreeCount = 0;
private:
    UPROPERTY(Transient) TArray<TObjectPtr<UProceduralMeshComponent>> MeshTiles;
    UPROPERTY(Transient) TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> TreeComponents;
    TMap<FString,float> AppliedHeights;
};
