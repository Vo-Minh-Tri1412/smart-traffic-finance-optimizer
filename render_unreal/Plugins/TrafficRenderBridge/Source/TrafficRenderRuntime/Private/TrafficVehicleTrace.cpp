#include "TrafficVehicleTrace.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TrafficRenderSchemas.h"

namespace
{
    bool StringField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, FString& Out)
    {
        return Object->TryGetStringField(Key, Out);
    }

    bool NumberField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, double& Out)
    {
        return Object->TryGetNumberField(Key, Out) && FMath::IsFinite(Out);
    }

    bool VehicleNumber(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, double& Out, const FString& VehicleId, FString& Error)
    {
        if (!NumberField(Object, Key, Out))
        {
            Error = FString::Printf(TEXT("vehicle '%s' missing numeric field '%s'"), *VehicleId, Key);
            return false;
        }
        return true;
    }
}

bool FTrafficVehicleTrace::ParseFrame(const FString& JsonLine, const int32 LineNumber, FTrafficVehicleTraceFrame& OutFrame, FString& OutError)
{
    OutFrame = FTrafficVehicleTraceFrame();
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonLine);
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = FString::Printf(TEXT("line %d: invalid JSON object"), LineNumber);
        return false;
    }
    if (!Root->TryGetStringField(TEXT("schema_version"), OutFrame.SchemaVersion) ||
        OutFrame.SchemaVersion != TrafficRenderSchemas::VehicleTrace)
    {
        OutError = FString::Printf(TEXT("line %d: unsupported or missing schema_version (expected %s)"),
            LineNumber, TrafficRenderSchemas::VehicleTrace);
        return false;
    }
    double Number = 0.0;
    if (!NumberField(Root, TEXT("timestep"), Number) || !NumberField(Root, TEXT("time_seconds"), OutFrame.TimeSeconds))
    {
        OutError = FString::Printf(TEXT("line %d: frame requires numeric timestep and time_seconds"), LineNumber);
        return false;
    }
    if (Number < 0.0 || Number != FMath::FloorToDouble(Number) || OutFrame.TimeSeconds < 0.0)
    {
        OutError = FString::Printf(TEXT("line %d: timestep must be a non-negative integer and time_seconds non-negative"), LineNumber);
        return false;
    }
    OutFrame.Timestep = static_cast<int64>(FMath::RoundToInt64(Number));
    StringField(Root, TEXT("district_id"), OutFrame.DistrictId);
    StringField(Root, TEXT("scenario_id"), OutFrame.ScenarioId);
    StringField(Root, TEXT("controller_id"), OutFrame.ControllerId);
    StringField(Root, TEXT("engine_id"), OutFrame.EngineId);

    const TArray<TSharedPtr<FJsonValue>>* Vehicles = nullptr;
    if (!Root->TryGetArrayField(TEXT("vehicles"), Vehicles) || !Vehicles)
    {
        OutError = FString::Printf(TEXT("line %d: frame requires vehicles array"), LineNumber);
        return false;
    }
    TSet<FString> FrameVehicleIds;
    for (const TSharedPtr<FJsonValue>& VehicleValue : *Vehicles)
    {
        const TSharedPtr<FJsonObject> Vehicle = VehicleValue.IsValid() ? VehicleValue->AsObject() : nullptr;
        if (!Vehicle.IsValid())
        {
            OutError = FString::Printf(TEXT("line %d: vehicles must contain objects"), LineNumber);
            return false;
        }
        FTrafficVehicleState State;
        if (!StringField(Vehicle, TEXT("vehicle_id"), State.VehicleId) || State.VehicleId.IsEmpty() ||
            !StringField(Vehicle, TEXT("vehicle_type"), State.VehicleType) || State.VehicleType.IsEmpty())
        {
            OutError = FString::Printf(TEXT("line %d: vehicle requires non-empty vehicle_id and vehicle_type"), LineNumber);
            return false;
        }
        if (!VehicleNumber(Vehicle, TEXT("x"), State.X, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("y"), State.Y, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("speed"), State.Speed, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("angle"), State.AngleDegrees, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("length_m"), State.LengthM, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("width_m"), State.WidthM, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("height_m"), State.HeightM, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("ground_clearance_m"), State.GroundClearanceM, State.VehicleId, OutError) ||
            !VehicleNumber(Vehicle, TEXT("elevation_m"), State.ElevationM, State.VehicleId, OutError))
        {
            return false;
        }
        StringField(Vehicle, TEXT("lane_id"), State.LaneId);
        StringField(Vehicle, TEXT("road_id"), State.RoadId);
        NumberField(Vehicle, TEXT("pos_lat_m"), State.PosLatM);
        NumberField(Vehicle, TEXT("lateral_speed_mps"), State.LateralSpeedMps);
        NumberField(Vehicle, TEXT("acceleration_mps2"), State.AccelerationMps2);
        StringField(Vehicle, TEXT("elevation_source"), State.ElevationSource);
        if (!StringField(Vehicle, TEXT("reference_point"), State.ReferencePoint) ||
            State.ReferencePoint != TrafficRenderSchemas::FrontBumperReferencePoint)
        {
            OutError = FString::Printf(TEXT("line %d vehicle '%s': reference_point must be %s"),
                LineNumber, *State.VehicleId, TrafficRenderSchemas::FrontBumperReferencePoint);
            return false;
        }
        if (State.LengthM <= 0.0 || State.WidthM <= 0.0 || State.HeightM <= 0.0 || State.GroundClearanceM < 0.0)
        {
            OutError = FString::Printf(TEXT("line %d vehicle '%s': invalid physical dimensions"), LineNumber, *State.VehicleId);
            return false;
        }
        if (FrameVehicleIds.Contains(State.VehicleId))
        {
            OutError = FString::Printf(TEXT("line %d: duplicate vehicle_id '%s'"), LineNumber, *State.VehicleId);
            return false;
        }
        FrameVehicleIds.Add(State.VehicleId);
        OutFrame.Vehicles.Add(MoveTemp(State));
    }
    return true;
}

bool FTrafficVehicleTrace::LoadJsonLines(const FString& TracePath, const int32 MaxFrames, FString& OutError)
{
    Frames.Reset();
    UniqueVehicleIds.Reset();
    Warnings.Reset();
    ParseErrorCount = 0;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *TracePath))
    {
        OutError = FString::Printf(TEXT("Cannot read vehicle trace: %s"), *TracePath);
        return false;
    }
    TArray<FString> Lines;
    Text.ParseIntoArrayLines(Lines, true);
    for (int32 Index = 0; Index < Lines.Num() && (MaxFrames <= 0 || Frames.Num() < MaxFrames); ++Index)
    {
        FTrafficVehicleTraceFrame Frame;
        FString Error;
        if (!ParseFrame(Lines[Index], Index + 1, Frame, Error))
        {
            ++ParseErrorCount;
            OutError = Error;
            return false;
        }
        if (Frames.Num() > 0 && Frame.TimeSeconds < Frames.Last().TimeSeconds)
        {
            OutError = FString::Printf(TEXT("line %d: vehicle trace time is not monotonic"), Index + 1);
            ++ParseErrorCount;
            return false;
        }
        for (const FTrafficVehicleState& Vehicle : Frame.Vehicles)
        {
            UniqueVehicleIds.Add(Vehicle.VehicleId);
        }
        Frames.Add(MoveTemp(Frame));
    }
    if (Frames.Num() == 0)
    {
        OutError = TEXT("vehicle trace contains no frames");
        return false;
    }
    return true;
}

double FTrafficVehicleTrace::StartTimeSeconds() const { return Frames.Num() ? Frames[0].TimeSeconds : 0.0; }
double FTrafficVehicleTrace::EndTimeSeconds() const { return Frames.Num() ? Frames.Last().TimeSeconds : 0.0; }

FTrafficVehicleTraceFrame FTrafficVehicleTrace::InterpolateFrame(
    const FTrafficVehicleTraceFrame& Left, const FTrafficVehicleTraceFrame& Right, const double Alpha, const double TimeSeconds)
{
    FTrafficVehicleTraceFrame Result = Left;
    Result.TimeSeconds = TimeSeconds;
    Result.Timestep = FMath::RoundToInt64(FMath::Lerp(static_cast<double>(Left.Timestep), static_cast<double>(Right.Timestep), Alpha));
    TMap<FString, const FTrafficVehicleState*> RightById;
    for (const FTrafficVehicleState& Vehicle : Right.Vehicles) RightById.Add(Vehicle.VehicleId, &Vehicle);
    for (FTrafficVehicleState& Vehicle : Result.Vehicles)
    {
        const FTrafficVehicleState* R = RightById.FindRef(Vehicle.VehicleId);
        if (!R) continue;
        Vehicle.X = FMath::Lerp(Vehicle.X, R->X, Alpha);
        Vehicle.Y = FMath::Lerp(Vehicle.Y, R->Y, Alpha);
        Vehicle.Speed = FMath::Lerp(Vehicle.Speed, R->Speed, Alpha);
        Vehicle.AngleDegrees += FMath::FindDeltaAngleDegrees(Vehicle.AngleDegrees, R->AngleDegrees) * Alpha;
        Vehicle.ElevationM = FMath::Lerp(Vehicle.ElevationM, R->ElevationM, Alpha);
        Vehicle.PosLatM = FMath::Lerp(Vehicle.PosLatM, R->PosLatM, Alpha);
        Vehicle.LateralSpeedMps = FMath::Lerp(Vehicle.LateralSpeedMps, R->LateralSpeedMps, Alpha);
        Vehicle.AccelerationMps2 = FMath::Lerp(Vehicle.AccelerationMps2, R->AccelerationMps2, Alpha);
    }
    return Result;
}

bool FTrafficVehicleTrace::Sample(const double TimeSeconds, FTrafficVehicleTraceFrame& OutFrame) const
{
    if (Frames.Num() == 0) return false;
    if (TimeSeconds <= StartTimeSeconds()) { OutFrame = Frames[0]; return true; }
    if (TimeSeconds >= EndTimeSeconds()) { OutFrame = Frames.Last(); return true; }
    int32 Low = 0, High = Frames.Num() - 1;
    while (Low + 1 < High)
    {
        const int32 Mid = (Low + High) / 2;
        if (Frames[Mid].TimeSeconds <= TimeSeconds) Low = Mid; else High = Mid;
    }
    const double Span = Frames[High].TimeSeconds - Frames[Low].TimeSeconds;
    const double Alpha = Span > SMALL_NUMBER ? (TimeSeconds - Frames[Low].TimeSeconds) / Span : 0.0;
    OutFrame = InterpolateFrame(Frames[Low], Frames[High], FMath::Clamp(Alpha, 0.0, 1.0), TimeSeconds);
    return true;
}
