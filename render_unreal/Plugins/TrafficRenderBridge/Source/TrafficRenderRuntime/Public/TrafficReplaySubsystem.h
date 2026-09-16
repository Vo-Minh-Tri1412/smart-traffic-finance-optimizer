#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SumoCoordinateTransform.h"
#include "TrafficPlaybackClock.h"
#include "TrafficRenderTypes.h"
#include "TrafficVehicleTrace.h"
#include "TrafficReplaySubsystem.generated.h"

UCLASS(BlueprintType)
class TRAFFICRENDERRUNTIME_API UTrafficReplaySubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Traffic Render")
    bool LoadRenderRun(const FString& ManifestPath, int32 MaxFrames, FString& OutError);

    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void Play();
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void Pause();
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void Seek(double TimeSeconds);
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") void AdvanceReplay(double DeltaSeconds);
    UFUNCTION(BlueprintPure, Category = "Traffic Render") bool IsPlaying() const;
    UFUNCTION(BlueprintPure, Category = "Traffic Render") double GetCurrentTimeSeconds() const;
    UFUNCTION(BlueprintPure, Category = "Traffic Render") FTrafficVehicleTraceFrame GetCurrentFrame() const;
    UFUNCTION(BlueprintPure, Category = "Traffic Render") FTrafficReplayQaSummary GetQaSummary() const;
    UFUNCTION(BlueprintCallable, Category = "Traffic Render") bool WriteQualityReport(const FString& OutputPath, FString& OutError) const;

    const FSumoCoordinateTransform& GetCoordinateTransform() const { return CoordinateTransform; }
    const FTrafficRenderRunManifest& GetManifest() const { return Manifest; }
    void RecordAppliedFrame(int32 ActiveVehicleCount, int32 DroppedVehicleCount);

private:
    FTrafficRenderRunManifest Manifest;
    FTrafficGeometryManifest Geometry;
    FTrafficVehicleTrace Trace;
    FTrafficPlaybackClock Clock;
    FSumoCoordinateTransform CoordinateTransform;
    FTrafficVehicleTraceFrame CurrentFrame;
    FTrafficReplayQaSummary QaSummary;

    void RefreshCurrentFrame();
};
