#include "TrafficCameraCalibration.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TrafficRenderSchemas.h"

namespace
{
    bool ReadVector3(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, FVector& Out)
    {
        const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
        if (!Object->TryGetArrayField(Key, Values) || !Values || Values->Num() != 3) return false;
        Out = FVector((*Values)[0]->AsNumber(), (*Values)[1]->AsNumber(), (*Values)[2]->AsNumber());
        return true;
    }

    bool ReadSize(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, FIntPoint& Out)
    {
        const TSharedPtr<FJsonObject>* Size = nullptr;
        double Width = 0.0, Height = 0.0;
        if (!Object->TryGetObjectField(Key, Size) || !Size || !Size->IsValid() ||
            !(*Size)->TryGetNumberField(TEXT("width"), Width) || !(*Size)->TryGetNumberField(TEXT("height"), Height)) return false;
        Out = FIntPoint(FMath::RoundToInt(Width), FMath::RoundToInt(Height));
        return Out.X > 0 && Out.Y > 0;
    }
}

bool FTrafficCameraCalibrationLoader::Load(
    const FString& Path,
    TArray<FTrafficCameraCalibration>& OutCameras,
    TArray<FString>& OutWarnings,
    FString& OutError)
{
    OutCameras.Reset();
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *Path))
    {
        OutError = FString::Printf(TEXT("Cannot read camera calibration: %s"), *Path);
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = TEXT("Camera calibration is not a JSON object");
        return false;
    }
    FString RootVersion, CoordinateSystem;
    if (!Root->TryGetStringField(TEXT("schema_version"), RootVersion) || RootVersion != TrafficRenderSchemas::CameraCalibration ||
        !Root->TryGetStringField(TEXT("coordinate_system"), CoordinateSystem) || CoordinateSystem != TEXT("sumo_xy_meters_z_up"))
    {
        OutError = FString::Printf(TEXT("Camera calibration requires schema %s and coordinate_system sumo_xy_meters_z_up"), TrafficRenderSchemas::CameraCalibration);
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>* Cameras = nullptr;
    if (!Root->TryGetArrayField(TEXT("cameras"), Cameras) || !Cameras)
    {
        OutError = TEXT("Camera calibration requires cameras array");
        return false;
    }
    for (int32 Index = 0; Index < Cameras->Num(); ++Index)
    {
        const TSharedPtr<FJsonObject> Object = (*Cameras)[Index].IsValid() ? (*Cameras)[Index]->AsObject() : nullptr;
        FTrafficCameraCalibration Camera;
        Camera.SchemaVersion = RootVersion;
        Camera.CoordinateSystem = CoordinateSystem;
        if (!Object.IsValid() || !Object->TryGetStringField(TEXT("camera_id"), Camera.CameraId) || Camera.CameraId.IsEmpty() ||
            !ReadVector3(Object, TEXT("position_m"), Camera.PositionMeters) ||
            !ReadSize(Object, TEXT("image_size"), Camera.ImageSize) ||
            !ReadSize(Object, TEXT("geometry_raster_size"), Camera.GeometryRasterSize))
        {
            OutError = FString::Printf(TEXT("camera index %d is missing id, position_m, or image sizes"), Index);
            return false;
        }
        Object->TryGetStringField(TEXT("role"), Camera.Role);
        const TSharedPtr<FJsonObject>* Rotation = nullptr;
        if (Object->TryGetObjectField(TEXT("rotation_degrees"), Rotation) && Rotation && Rotation->IsValid())
        {
            double Yaw = 0.0, Pitch = 0.0, Roll = 0.0;
            (*Rotation)->TryGetNumberField(TEXT("yaw"), Yaw);
            (*Rotation)->TryGetNumberField(TEXT("pitch"), Pitch);
            (*Rotation)->TryGetNumberField(TEXT("roll"), Roll);
            Camera.RotationDegrees = FRotator(static_cast<float>(Pitch), static_cast<float>(Yaw), static_cast<float>(Roll));
        }
        const TSharedPtr<FJsonObject>* Intrinsics = nullptr;
        if (!Object->TryGetObjectField(TEXT("intrinsics"), Intrinsics) || !Intrinsics || !Intrinsics->IsValid() ||
            !(*Intrinsics)->TryGetNumberField(TEXT("fx"), Camera.Fx) || !(*Intrinsics)->TryGetNumberField(TEXT("fy"), Camera.Fy) ||
            !(*Intrinsics)->TryGetNumberField(TEXT("cx"), Camera.Cx) || !(*Intrinsics)->TryGetNumberField(TEXT("cy"), Camera.Cy))
        {
            OutError = FString::Printf(TEXT("camera '%s' requires numeric intrinsics"), *Camera.CameraId);
            return false;
        }
        Object->TryGetNumberField(TEXT("near_clip_m"), Camera.NearClipMeters);
        Object->TryGetNumberField(TEXT("far_clip_m"), Camera.FarClipMeters);
        Object->TryGetNumberField(TEXT("capture_interval_seconds"), Camera.CaptureIntervalSeconds);
        if (Camera.Fx <= 0.0 || Camera.Fy <= 0.0 || Camera.NearClipMeters <= 0.0 || Camera.FarClipMeters <= Camera.NearClipMeters || Camera.CaptureIntervalSeconds <= 0.0)
        {
            OutError = FString::Printf(TEXT("camera '%s' has invalid intrinsics/clipping/capture interval"), *Camera.CameraId);
            return false;
        }
        const TArray<TSharedPtr<FJsonValue>>* LaneIds = nullptr;
        if (Object->TryGetArrayField(TEXT("target_lane_ids"), LaneIds) && LaneIds)
        {
            for (const TSharedPtr<FJsonValue>& Lane : *LaneIds) Camera.TargetLaneIds.Add(Lane->AsString());
        }
        OutCameras.Add(MoveTemp(Camera));
    }
    if (OutCameras.Num() == 0) OutWarnings.Add(TEXT("Camera calibration contains no cameras"));
    return true;
}
