#include "TrafficRenderTypes.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

FString FTrafficReplayQaSummary::ToJson() const
{
    const TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetBoolField(TEXT("success"), bSuccess);
    Root->SetBoolField(TEXT("manifest_loaded"), bManifestLoaded);
    Root->SetStringField(TEXT("run_id"), RunId);
    Root->SetStringField(TEXT("trace_schema_version"), TraceSchemaVersion);
    Root->SetNumberField(TEXT("loaded_frame_count"), LoadedFrameCount);
    Root->SetNumberField(TEXT("frames_applied"), FramesApplied);
    Root->SetNumberField(TEXT("unique_vehicle_count"), UniqueVehicleCount);
    Root->SetNumberField(TEXT("largest_active_vehicle_count"), LargestActiveVehicleCount);
    Root->SetNumberField(TEXT("dropped_debug_vehicle_count"), DroppedDebugVehicleCount);
    Root->SetNumberField(TEXT("parse_error_count"), ParseErrorCount);
    const TSharedRef<FJsonObject> Origin = MakeShared<FJsonObject>();
    Origin->SetNumberField(TEXT("x"), LocalOriginMeters.X);
    Origin->SetNumberField(TEXT("y"), LocalOriginMeters.Y);
    Root->SetObjectField(TEXT("local_origin_meters"), Origin);
    TArray<TSharedPtr<FJsonValue>> WarningValues;
    for (const FString& Warning : Warnings) WarningValues.Add(MakeShared<FJsonValueString>(Warning));
    Root->SetArrayField(TEXT("warnings"), WarningValues);
    FString Result;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result);
    FJsonSerializer::Serialize(Root, Writer);
    return Result + TEXT("\n");
}
