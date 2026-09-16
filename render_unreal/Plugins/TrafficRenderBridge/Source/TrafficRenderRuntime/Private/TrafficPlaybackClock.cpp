#include "TrafficPlaybackClock.h"

#include "Math/UnrealMathUtility.h"

void FTrafficPlaybackClock::Configure(const double InStartTime, const double InEndTime, const double InSpeed, const bool bInLoop)
{
    StartTimeSeconds = FMath::Min(InStartTime, InEndTime);
    EndTimeSeconds = FMath::Max(InStartTime, InEndTime);
    CurrentTimeSeconds = StartTimeSeconds;
    PlaybackSpeed = FMath::Max(0.0, InSpeed);
    bLoop = bInLoop;
    bPlaying = false;
}

void FTrafficPlaybackClock::Play() { bPlaying = true; }
void FTrafficPlaybackClock::Pause() { bPlaying = false; }

void FTrafficPlaybackClock::Restart()
{
    CurrentTimeSeconds = StartTimeSeconds;
    bPlaying = false;
}

void FTrafficPlaybackClock::Seek(const double TimeSeconds)
{
    CurrentTimeSeconds = FMath::Clamp(TimeSeconds, StartTimeSeconds, EndTimeSeconds);
}

double FTrafficPlaybackClock::Advance(const double DeltaSeconds)
{
    if (!bPlaying || DeltaSeconds <= 0.0 || EndTimeSeconds <= StartTimeSeconds)
    {
        return CurrentTimeSeconds;
    }

    const double Next = CurrentTimeSeconds + DeltaSeconds * PlaybackSpeed;
    if (Next <= EndTimeSeconds)
    {
        CurrentTimeSeconds = Next;
    }
    else if (bLoop)
    {
        const double Duration = DurationSeconds();
        CurrentTimeSeconds = Duration > 0.0
            ? StartTimeSeconds + FMath::Fmod(Next - StartTimeSeconds, Duration)
            : StartTimeSeconds;
    }
    else
    {
        CurrentTimeSeconds = EndTimeSeconds;
        bPlaying = false;
    }
    return CurrentTimeSeconds;
}

double FTrafficPlaybackClock::DurationSeconds() const
{
    return FMath::Max(0.0, EndTimeSeconds - StartTimeSeconds);
}
