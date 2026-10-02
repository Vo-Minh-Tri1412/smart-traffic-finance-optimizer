#pragma once

#include "CoreMinimal.h"
#include "TrafficRenderTypes.h"

class TRAFFICRENDERRUNTIME_API FTrafficVehicleTrace
{
public:
    TArray<FTrafficVehicleTraceFrame> Frames;
    TSet<FString> UniqueVehicleIds;
    TArray<FString> Warnings;
    int32 ParseErrorCount = 0;

    bool LoadJsonLines(const FString& TracePath, int32 MaxFrames, FString& OutError);
    bool Sample(double TimeSeconds, FTrafficVehicleTraceFrame& OutFrame) const;

    double StartTimeSeconds() const;
    double EndTimeSeconds() const;

    static bool ParseFrame(
        const FString& JsonLine,
        int32 LineNumber,
        FTrafficVehicleTraceFrame& OutFrame,
        FString& OutError);

private:
    static FTrafficVehicleTraceFrame InterpolateFrame(
        const FTrafficVehicleTraceFrame& Left,
        const FTrafficVehicleTraceFrame& Right,
        double Alpha,
        double TimeSeconds);
};
