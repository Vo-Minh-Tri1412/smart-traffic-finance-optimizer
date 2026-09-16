#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TrafficReplayController.generated.h"

class ATrafficReplayVehicleActor;
class UTrafficReplaySubsystem;

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API ATrafficReplayController : public AActor
{
    GENERATED_BODY()

public:
    ATrafficReplayController();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    bool LoadRenderRun(const FString& InManifestPath, int32 MaxFrames, FString& OutError);

    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void Play();
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void Pause();
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void Seek(double TimeSeconds);
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") bool ExportQualityReport(const FString& OutputPath, FString& OutError) const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render") FString ManifestPath;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render") bool bAutoLoad = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render") bool bAutoPlay = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render") bool bSpawnDebugVehicles = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic Render", meta = (ClampMin = "1")) int32 MaxDebugVehicles = 2000;

private:
    UPROPERTY(Transient) TMap<FString, TObjectPtr<ATrafficReplayVehicleActor>> VehicleActors;

    UTrafficReplaySubsystem* GetReplaySubsystem() const;
    void ApplyCurrentFrame();
    void ClearVehicles();
};
