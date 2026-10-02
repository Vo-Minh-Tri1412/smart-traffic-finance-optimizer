#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "TrafficLiveProfile.generated.h"

class UStaticMesh;
class UMaterialInterface;
class ATrafficReplayVehicleActor;
class UTrafficUrbanSceneProfile;

UENUM(BlueprintType)
enum class ETrafficVisualForwardAxis : uint8 { PositiveX, PositiveY, NegativeX, NegativeY };

USTRUCT(BlueprintType)
struct TRAFFICRENDERRUNTIME_API FTrafficVehicleVisualDefinition
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle") FString VehicleType = TEXT("*");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle", meta=(AssetBundles="Live"))
    TArray<TSoftObjectPtr<UStaticMesh>> MeshParts;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle", meta=(AssetBundles="Live"))
    TSoftObjectPtr<UMaterialInterface> MaterialOverride;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle", meta=(AssetBundles="Live"))
    TSoftClassPtr<ATrafficReplayVehicleActor> ActorClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle")
    ETrafficVisualForwardAxis ForwardAxis = ETrafficVisualForwardAxis::PositiveX;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicle")
    bool PreserveAspectRatio = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Provenance") FString Source;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Provenance") FString License;
};

/** Authoritative Editor references for the live renderer's assets. */
UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficLiveAssetCatalog : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Vehicles") TArray<FTrafficVehicleVisualDefinition> Vehicles;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Road", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> RoadMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground", meta=(AssetBundles="Live")) TSoftObjectPtr<UStaticMesh> GroundMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> GroundMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UStaticMesh> SignalPoleMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UStaticMesh> SignalHousingMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UStaticMesh> SignalLensMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> SignalRed;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> SignalYellow;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> SignalGreen;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(AssetBundles="Live")) TSoftObjectPtr<UMaterialInterface> SignalInactive;
};

/** Visual placement only: source lane geometry and TLS linkIndex remain SUMO-owned. */
UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficLivePlacementProfile : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(ClampMin="0")) float SignalHeightMeters = 3.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(ClampMin="0")) float RoadsideClearanceMeters = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals", meta=(ClampMin="0")) float HeadSpacingMeters = 0.75f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals") FVector PoleDimensionsMeters = FVector(0.08,0.08,3.5);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals") FVector HousingDimensionsMeters = FVector(0.3,0.85,1.25);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals") FVector LensDimensionsMeters = FVector(0.35);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals") FVector HousingOffsetMeters = FVector(-0.2,0,0);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Signals") float LensVerticalSpacingMeters = 0.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground") float GroundTopMeters = -0.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Ground", meta=(ClampMin="0")) float GroundMarginMeters = 100;
};

/** Camera, lighting and references: editable in the Content Browser without rebuilding C++. */
UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficLiveSceneProfile : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Profiles", meta=(AssetBundles="Live")) TSoftObjectPtr<UTrafficLiveAssetCatalog> Catalog;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Profiles", meta=(AssetBundles="Live")) TSoftObjectPtr<UTrafficLivePlacementProfile> Placement;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Profiles", meta=(AssetBundles="Live")) TSoftObjectPtr<UTrafficUrbanSceneProfile> UrbanEnvironment;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") FVector FollowOffsetMeters = FVector(-17,-17,15);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") FVector JunctionOffsetMeters = FVector(-30,-30,22);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera", meta=(ClampMin="10",ClampMax="150")) float FieldOfView = 65;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera", meta=(ClampMin="0.1")) float CameraSpeedMetersPerSecond = 25;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera") bool FollowVehicle = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Lighting") FRotator SunRotation = FRotator(-60,-35,0);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Lighting", meta=(ClampMin="0")) float SunIntensity = 5;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Lighting", meta=(ClampMin="0")) float SkyIntensity = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Lighting", meta=(ClampMin="0.01")) float FixedExposure = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Presentation") bool CastShadows = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Presentation") bool ShowStatus = true;
};
