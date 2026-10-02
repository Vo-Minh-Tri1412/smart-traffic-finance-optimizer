#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SumoCoordinateTransform.h"
#include "TrafficRenderTypes.h"
#include "TrafficLiveProfile.h"
#include "TrafficLiveController.generated.h"

class FSocket;
class FJsonObject;
class ACameraActor;
class ATrafficSumoGeometryActor;
class UStaticMeshComponent;
class UStaticMesh;
class USceneComponent;
class UMaterialInterface;
struct FStreamableHandle;
class ATrafficReplayVehicleActor;
class ATrafficUrbanEnvironment;
class UTrafficUrbanSceneProfile;

/** Local TCP consumer of live SUMO poses and signal states. SUMO owns all motion. */
UCLASS(BlueprintType, Blueprintable)
class TRAFFICRENDERRUNTIME_API ATrafficLiveController : public AActor
{
    GENERATED_BODY()
public:
    ATrafficLiveController();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="SUMO Live")
    TSoftObjectPtr<UTrafficLiveSceneProfile> SceneProfile;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="SUMO Live", meta=(ClampMin="1",ClampMax="65535"))
    int32 BridgePort = 0;
    UFUNCTION(BlueprintImplementableEvent, Category="SUMO Live")
    void OnLiveFrameApplied(const FTrafficVehicleTraceFrame& Frame);
    UFUNCTION(BlueprintCallable, Category="SUMO Live")
    void SetFollowVehicle(bool Enabled) { bFollow = Enabled; }
    UFUNCTION(BlueprintPure, Category="SUMO Live")
    double GetSimulationTime() const { return LastFrame.TimeSeconds; }

private:
    FSocket* Socket = nullptr;
    TArray<uint8> ReceiveBuffer;
    FSumoCoordinateTransform Transform;
    UPROPERTY(Transient) TObjectPtr<ACameraActor> Camera;
    UPROPERTY(Transient) TObjectPtr<ATrafficSumoGeometryActor> Roads;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> RedMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> YellowMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> GreenMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> DarkMaterial;
    UPROPERTY(Transient) TMap<FString, TObjectPtr<ATrafficReplayVehicleActor>> Vehicles;
    UPROPERTY(Transient) TObjectPtr<UTrafficLiveSceneProfile> LoadedScene;
    UPROPERTY(Transient) TObjectPtr<UTrafficLiveAssetCatalog> Catalog;
    UPROPERTY(Transient) TObjectPtr<UTrafficLivePlacementProfile> Placement;
    UPROPERTY(Transient) TObjectPtr<UTrafficUrbanSceneProfile> UrbanProfile;
    UPROPERTY(Transient) TObjectPtr<ATrafficUrbanEnvironment> UrbanActor;
    TSharedPtr<FStreamableHandle> AssetLoad;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> SignalMeshes;
    TArray<FString> SignalTlsIds;
    TArray<int32> SignalIndices;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> RedLenses;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> YellowLenses;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> GreenLenses;
    TMap<FString, FString> PreviousSignalStates;
    FTrafficVehicleTraceFrame LastFrame;
    FString RunId, ReportPath, CaptureDirectory, FollowId, Failure;
    int32 Port = 0, FramesReceived = 0, SignalChanges = 0, PoseChanges = 0, MaxVehicles = 0;
    double RetryAt = 0, LastFrameWallTime = 0;
    bool bReady = false, bComplete = false, bFollow = true, bCaptureFirst = false, bCaptureSecond = false;
    bool bAutoExit = false;
    FVector Focus = FVector::ZeroVector;
    FVector JunctionFocus = FVector::ZeroVector;
    bool bJunctionFocus = false, bLoadingAssets = false;
    double ReadyWallTime = 0, NextCaptureAt = 0, RecordSeconds = 0;
    int32 CaptureCount = 0;

    void Connect();
    void Receive();
    void HandlePacket(const FString& Line);
    bool InitializeScene(const TSharedPtr<FJsonObject>& Packet, FString& Error);
    void ApplyFrame(const TSharedPtr<FJsonObject>& Packet);
    void UpdateCamera(float DeltaSeconds);
    void WriteReport() const;
    void Fail(const FString& Error);
    UStaticMeshComponent* AddMesh(const FString& Name, UStaticMesh* Asset, const FTransform& Pose, UMaterialInterface* Material);
    void LoadPresentation(const TSharedPtr<FJsonObject>& Packet);
    void WriteVisualSnapshot() const;
};
