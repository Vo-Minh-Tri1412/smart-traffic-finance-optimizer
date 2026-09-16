#pragma once

#include "CoreMinimal.h"

struct TRAFFICRENDERRUNTIME_API FTrafficPlaybackClock
{
    double StartTimeSeconds = 0.0;
    double EndTimeSeconds = 0.0;
    double CurrentTimeSeconds = 0.0;
    double PlaybackSpeed = 1.0;
    bool bLoop = true;
    bool bPlaying = false;

    void Configure(double InStartTime, double InEndTime, double InSpeed = 1.0, bool bInLoop = true);
    void Play();
    void Pause();
    void Restart();
    void Seek(double TimeSeconds);
    double Advance(double DeltaSeconds);
    double DurationSeconds() const;
};
