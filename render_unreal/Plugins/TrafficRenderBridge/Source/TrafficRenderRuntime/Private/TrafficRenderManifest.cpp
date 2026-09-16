#include "TrafficRenderManifest.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TrafficRenderSchemas.h"

namespace
{
    bool ReadJsonObject(const FString& Path, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
    {
        FString Text;
        if (!FFileHelper::LoadFileToString(Text, *Path))
        {
            OutError = FString::Printf(TEXT("Cannot read JSON artifact: %s"), *Path);
            return false;
        }
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
        if (!FJsonSerializer::Deserialize(Reader, OutObject) || !OutObject.IsValid())
        {
            OutError = FString::Printf(TEXT("Invalid JSON object: %s"), *Path);
            return false;
        }
        return true;
    }

    bool RequiredString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, FString& Out, FString& OutError)
    {
        if (!Object->TryGetStringField(Key, Out) || Out.IsEmpty())
        {
            OutError = FString::Printf(TEXT("Missing required non-empty string field '%s'"), Key);
            return false;
        }
        return true;
    }

    bool Number(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, double& Out)
    {
        return Object->TryGetNumberField(Key, Out);
    }

    bool ParseBounds(const TSharedPtr<FJsonObject>& Object, FVector2D& OutMin, FVector2D& OutMax, FString& OutError)
    {
        const TSharedPtr<FJsonObject>* Bounds = nullptr;
        if (!Object->TryGetObjectField(TEXT("bounds"), Bounds) || !Bounds || !Bounds->IsValid())
        {
            OutError = TEXT("geometry manifest requires a bounds object");
            return false;
        }
        double MinX = 0.0, MinY = 0.0, MaxX = 0.0, MaxY = 0.0;
        if (!Number(*Bounds, TEXT("min_x"), MinX) || !Number(*Bounds, TEXT("min_y"), MinY) ||
            !Number(*Bounds, TEXT("max_x"), MaxX) || !Number(*Bounds, TEXT("max_y"), MaxY) ||
            MaxX < MinX || MaxY < MinY)
        {
            OutError = TEXT("geometry manifest bounds are missing, non-numeric, or inverted");
            return false;
        }
        OutMin = FVector2D(static_cast<float>(MinX), static_cast<float>(MinY));
        OutMax = FVector2D(static_cast<float>(MaxX), static_cast<float>(MaxY));
        return true;
    }
}

FString FTrafficRenderManifestLoader::ResolveArtifactPath(const FString& OwnerPath, const FString& ArtifactPath)
{
    if (ArtifactPath.IsEmpty())
    {
        return FString();
    }
    return FPaths::ConvertRelativePathToFull(
        FPaths::IsRelative(ArtifactPath) ? FPaths::Combine(FPaths::GetPath(OwnerPath), ArtifactPath) : ArtifactPath);
}

bool FTrafficRenderManifestLoader::LoadGeometryManifest(
    const FString& GeometryManifestPath,
    FTrafficGeometryManifest& OutGeometry,
    TArray<FString>& OutWarnings,
    FString& OutError)
{
    TSharedPtr<FJsonObject> Object;
    if (!ReadJsonObject(GeometryManifestPath, Object, OutError))
    {
        return false;
    }
    if (!RequiredString(Object, TEXT("schema_version"), OutGeometry.SchemaVersion, OutError) ||
        OutGeometry.SchemaVersion != TrafficRenderSchemas::GeometryManifest)
    {
        OutError = FString::Printf(TEXT("Unsupported geometry schema '%s' (expected %s)"),
            *OutGeometry.SchemaVersion, TrafficRenderSchemas::GeometryManifest);
        return false;
    }
    if (!RequiredString(Object, TEXT("geometry_source"), OutGeometry.GeometrySource, OutError) ||
        !RequiredString(Object, TEXT("coordinate_system"), OutGeometry.CoordinateSystem, OutError) ||
        OutGeometry.CoordinateSystem != TrafficRenderSchemas::SumoCoordinateSystem)
    {
        OutError = FString::Printf(TEXT("Geometry coordinate_system must be %s"), TrafficRenderSchemas::SumoCoordinateSystem);
        return false;
    }
    FString NetXml;
    if (!RequiredString(Object, TEXT("net_xml"), NetXml, OutError) ||
        !ParseBounds(Object, OutGeometry.BoundsMin, OutGeometry.BoundsMax, OutError))
    {
        return false;
    }
    OutGeometry.NetXmlPath = ResolveArtifactPath(GeometryManifestPath, NetXml);
    if (!FPaths::FileExists(OutGeometry.NetXmlPath))
    {
        OutWarnings.Add(FString::Printf(TEXT("Declared net_xml does not exist: %s"), *OutGeometry.NetXmlPath));
    }
    double Count = 0.0;
    if (Number(Object, TEXT("lane_count"), Count)) OutGeometry.LaneCount = FMath::Max(0, FMath::RoundToInt(Count));
    if (Number(Object, TEXT("junction_count"), Count)) OutGeometry.JunctionCount = FMath::Max(0, FMath::RoundToInt(Count));

    const TSharedPtr<FJsonObject>* OriginObject = nullptr;
    if (Object->TryGetObjectField(TEXT("local_origin"), OriginObject) && OriginObject && OriginObject->IsValid())
    {
        double X = 0.0, Y = 0.0;
        if (Number(*OriginObject, TEXT("x"), X) && Number(*OriginObject, TEXT("y"), Y))
        {
            OutGeometry.LocalOriginMeters = FVector2D(static_cast<float>(X), static_cast<float>(Y));
        }
        else
        {
            OutWarnings.Add(TEXT("local_origin object is invalid; using bounds.min as origin"));
            OutGeometry.LocalOriginMeters = OutGeometry.BoundsMin;
        }
    }
    else
    {
        OutGeometry.LocalOriginMeters = OutGeometry.BoundsMin;
        OutWarnings.Add(TEXT("geometry manifest omitted local_origin; using bounds.min explicitly"));
    }
    return true;
}

bool FTrafficRenderManifestLoader::LoadRenderRunManifest(
    const FString& ManifestPath,
    FTrafficRenderRunManifest& OutManifest,
    FTrafficGeometryManifest& OutGeometry,
    TArray<FString>& OutWarnings,
    FString& OutError)
{
    TSharedPtr<FJsonObject> Object;
    if (!ReadJsonObject(ManifestPath, Object, OutError))
    {
        return false;
    }
    if (!RequiredString(Object, TEXT("schema_version"), OutManifest.SchemaVersion, OutError) ||
        OutManifest.SchemaVersion != TrafficRenderSchemas::RenderRunManifest)
    {
        OutError = FString::Printf(TEXT("Unsupported render manifest schema '%s' (expected %s)"),
            *OutManifest.SchemaVersion, TrafficRenderSchemas::RenderRunManifest);
        return false;
    }
    if (!RequiredString(Object, TEXT("run_id"), OutManifest.RunId, OutError) ||
        !RequiredString(Object, TEXT("geometry_manifest"), OutManifest.GeometryManifestPath, OutError) ||
        !RequiredString(Object, TEXT("vehicle_trace"), OutManifest.VehicleTracePath, OutError) ||
        !RequiredString(Object, TEXT("renderer"), OutManifest.Renderer, OutError))
    {
        return false;
    }
    OutManifest.ManifestPath = FPaths::ConvertRelativePathToFull(ManifestPath);
    OutManifest.GeometryManifestPath = ResolveArtifactPath(ManifestPath, OutManifest.GeometryManifestPath);
    OutManifest.VehicleTracePath = ResolveArtifactPath(ManifestPath, OutManifest.VehicleTracePath);
    auto ResolveOptional = [&](const TCHAR* Key, FString& OutPath)
    {
        FString Value;
        if (Object->TryGetStringField(Key, Value) && !Value.IsEmpty())
        {
            OutPath = ResolveArtifactPath(ManifestPath, Value);
            if (!FPaths::FileExists(OutPath))
            {
                OutWarnings.Add(FString::Printf(TEXT("Declared %s does not exist: %s"), Key, *OutPath));
            }
        }
    };
    ResolveOptional(TEXT("traffic_light_trace"), OutManifest.TrafficLightTracePath);
    ResolveOptional(TEXT("semantic_overlay"), OutManifest.SemanticOverlayPath);
    ResolveOptional(TEXT("event_trace"), OutManifest.EventTracePath);
    ResolveOptional(TEXT("quality_report"), OutManifest.QualityReportPath);
    if (!FPaths::FileExists(OutManifest.VehicleTracePath))
    {
        OutWarnings.Add(FString::Printf(TEXT("Declared vehicle_trace does not exist: %s"), *OutManifest.VehicleTracePath));
    }
    if (!LoadGeometryManifest(OutManifest.GeometryManifestPath, OutGeometry, OutWarnings, OutError))
    {
        return false;
    }
    if (OutManifest.Renderer != TEXT("unreal"))
    {
        OutWarnings.Add(FString::Printf(TEXT("Manifest renderer is '%s'; Unreal adapter is running it explicitly"), *OutManifest.Renderer));
    }
    return true;
}
