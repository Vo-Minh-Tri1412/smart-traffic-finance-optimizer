#include "TrafficSumoGeometryActor.h"

#include "ProceduralMeshComponent.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "TrafficRenderManifest.h"
#include "TrafficRenderSchemas.h"
#include "SumoCoordinateTransform.h"
#include "XmlFile.h"

namespace
{
    struct FTileMeshData
    {
        FVector OriginCm = FVector::ZeroVector;
        TArray<FVector> Vertices;
        TArray<int32> Triangles;
        TArray<FVector> Normals;
        TArray<FVector2D> UVs;
        TArray<FLinearColor> Colors;
        TArray<FProcMeshTangent> Tangents;
    };

    bool ParseShape(const FString& Shape, TArray<FVector2D>& Points)
    {
        TArray<FString> Tokens;
        Shape.ParseIntoArray(Tokens, TEXT(" "), true);
        for (const FString& Token : Tokens)
        {
            TArray<FString> Pair;
            Token.ParseIntoArray(Pair, TEXT(","), true);
            if (Pair.Num() < 2) return false;
            Points.Add(FVector2D(FCString::Atod(*Pair[0]), FCString::Atod(*Pair[1])));
        }
        return Points.Num() >= 2;
    }
}

ATrafficSumoGeometryActor::ATrafficSumoGeometryActor()
{
    PrimaryActorTick.bCanEverTick = false;
    RoadMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RoadMesh"));
    SetRootComponent(RoadMesh);
    RoadMesh->bUseAsyncCooking = true;
    RoadMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

bool ATrafficSumoGeometryActor::BuildFromGeometryManifest(const FString& InGeometryManifestPath, const int32 MaxLanes, FString& OutError)
{
    if (MaxLanes < 0)
    {
        OutError = TEXT("MaxLanes must be non-negative; zero builds the full map");
        return false;
    }
    if (!FMath::IsFinite(TileSizeMeters) || TileSizeMeters < 100.0f)
    {
        OutError = TEXT("Road tile size must be finite and at least 100 metres");
        return false;
    }
    if (!FMath::IsFinite(TextureRepeatMeters) || TextureRepeatMeters < 0.1f)
    {
        OutError = TEXT("Road texture repeat distance must be finite and at least 0.1 metre");
        return false;
    }
    FTrafficGeometryManifest Geometry;
    TArray<FString> Warnings;
    if (!FTrafficRenderManifestLoader::LoadGeometryManifest(InGeometryManifestPath, Geometry, Warnings, OutError)) return false;
    if (!FPaths::FileExists(Geometry.NetXmlPath))
    {
        OutError = FString::Printf(TEXT("SUMO net XML does not exist: %s"), *Geometry.NetXmlPath);
        return false;
    }
    FString XmlText;
    if (!FFileHelper::LoadFileToString(XmlText, *Geometry.NetXmlPath))
    {
        OutError = FString::Printf(TEXT("Cannot read SUMO net XML: %s"), *Geometry.NetXmlPath);
        return false;
    }
    const FXmlFile XmlFile(XmlText, EConstructMethod::ConstructFromBuffer);
    const FXmlNode* Root = XmlFile.GetRootNode();
    if (!Root)
    {
        OutError = TEXT("SUMO net XML has no root node");
        return false;
    }
    TMap<FIntPoint, FTileMeshData> TileBuffers;
    TotalLaneCount = RenderedLaneCount = RenderedSegmentCount = JunctionCount = 0;
    SkippedDegenerateSegmentCount = 0;
    RenderedTileCount = 0;
    LocalOriginMeters = Geometry.LocalOriginMeters;
    const FSumoCoordinateTransform Transform(LocalOriginMeters);
    for (const FXmlNode* Child : Root->GetChildrenNodes())
    {
        if (Child->GetTag() == TEXT("junction")) { ++JunctionCount; continue; }
        if (Child->GetTag() != TEXT("edge")) continue;
        for (const FXmlNode* Lane : Child->GetChildrenNodes())
        {
            if (Lane->GetTag() != TEXT("lane")) continue;
            ++TotalLaneCount;
            if (MaxLanes > 0 && RenderedLaneCount >= MaxLanes) continue;
            TArray<FVector2D> Shape;
            if (!ParseShape(Lane->GetAttribute(TEXT("shape")), Shape)) continue;
            double Width = 3.2;
            if (!Lane->GetAttribute(TEXT("width")).IsEmpty()) Width = FCString::Atod(*Lane->GetAttribute(TEXT("width")));
            Width = FMath::Max(0.1, Width);
            double DistanceAlongLaneMeters = 0.0;
            for (int32 PointIndex = 0; PointIndex + 1 < Shape.Num(); ++PointIndex)
            {
                const FVector2D A = Shape[PointIndex];
                const FVector2D B = Shape[PointIndex + 1];
                const FVector2D Delta = B - A;
                if (Delta.IsNearlyZero())
                {
                    ++SkippedDegenerateSegmentCount;
                    continue;
                }
                const FVector2D Side = Delta.GetSafeNormal().GetRotated(90.0) * static_cast<float>(Width * 0.5);
                const double SegmentLengthMeters = Delta.Size();
                const float UStart = static_cast<float>(DistanceAlongLaneMeters / TextureRepeatMeters);
                const float UEnd = static_cast<float>((DistanceAlongLaneMeters + SegmentLengthMeters) / TextureRepeatMeters);
                const float VEnd = static_cast<float>(Width / TextureRepeatMeters);
                const FVector2D Midpoint = (A + B) * 0.5;
                const FIntPoint TileKey(
                    FMath::FloorToInt((Midpoint.X - LocalOriginMeters.X) / TileSizeMeters),
                    FMath::FloorToInt((Midpoint.Y - LocalOriginMeters.Y) / TileSizeMeters));
                FTileMeshData& Tile = TileBuffers.FindOrAdd(TileKey);
                Tile.OriginCm = Transform.SumoPointToUnreal(
                    LocalOriginMeters.X + static_cast<double>(TileKey.X) * TileSizeMeters,
                    LocalOriginMeters.Y + static_cast<double>(TileKey.Y) * TileSizeMeters);
                const int32 Base = Tile.Vertices.Num();
                Tile.Vertices.Add(Transform.SumoPointToUnreal(A.X + Side.X, A.Y + Side.Y) - Tile.OriginCm);
                Tile.Vertices.Add(Transform.SumoPointToUnreal(B.X + Side.X, B.Y + Side.Y) - Tile.OriginCm);
                Tile.Vertices.Add(Transform.SumoPointToUnreal(B.X - Side.X, B.Y - Side.Y) - Tile.OriginCm);
                Tile.Vertices.Add(Transform.SumoPointToUnreal(A.X - Side.X, A.Y - Side.Y) - Tile.OriginCm);
                Tile.Triangles.Add(Base);
                Tile.Triangles.Add(Base + 1);
                Tile.Triangles.Add(Base + 2);
                Tile.Triangles.Add(Base);
                Tile.Triangles.Add(Base + 2);
                Tile.Triangles.Add(Base + 3);
                for (int32 VertexIndex = 0; VertexIndex < 4; ++VertexIndex)
                {
                    Tile.Normals.Add(FVector::UpVector);
                    Tile.UVs.Add(FVector2D(
                        VertexIndex == 1 || VertexIndex == 2 ? UEnd : UStart,
                        VertexIndex >= 2 ? VEnd : 0.0f));
                    Tile.Colors.Add(FLinearColor::White);
                    Tile.Tangents.Add(FProcMeshTangent(FVector::ForwardVector, false));
                }
                DistanceAlongLaneMeters += SegmentLengthMeters;
                ++RenderedSegmentCount;
            }
            ++RenderedLaneCount;
        }
    }
    RoadMesh->ClearAllMeshSections();
    for (TObjectPtr<UProceduralMeshComponent>& TileMesh : TileMeshes)
    {
        if (TileMesh) TileMesh->DestroyComponent();
    }
    TileMeshes.Reset();
    TArray<FIntPoint> TileKeys;
    TileBuffers.GetKeys(TileKeys);
    TileKeys.Sort([](const FIntPoint& Left, const FIntPoint& Right)
    {
        return Left.X == Right.X ? Left.Y < Right.Y : Left.X < Right.X;
    });
    for (const FIntPoint& TileKey : TileKeys)
    {
        FTileMeshData& Tile = TileBuffers.FindChecked(TileKey);
        UProceduralMeshComponent* TileMesh = NewObject<UProceduralMeshComponent>(this);
        TileMesh->SetupAttachment(RoadMesh);
        TileMesh->SetRelativeLocation(Tile.OriginCm);
        TileMesh->bUseAsyncCooking = true;
        TileMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        AddInstanceComponent(TileMesh);
        TileMesh->RegisterComponent();
        TileMesh->CreateMeshSection_LinearColor(
            0, Tile.Vertices, Tile.Triangles, Tile.Normals, Tile.UVs, Tile.Colors, Tile.Tangents, false);
        if (RoadMaterial) TileMesh->SetMaterial(0, RoadMaterial);
        TileMeshes.Add(TileMesh);
    }
    RenderedTileCount = TileMeshes.Num();
    if (RenderedTileCount == 0)
    {
        OutError = TEXT("SUMO net contains no renderable lane segments");
        return false;
    }
    GeometryManifestPath = InGeometryManifestPath;
    PreviewMaxLanes = MaxLanes;
    return true;
}

bool ATrafficSumoGeometryActor::RebuildConfiguredGeometry(FString& OutError)
{
    if (GeometryManifestPath.IsEmpty())
    {
        OutError = TEXT("Set a geometry manifest path before rebuilding the retained map");
        return false;
    }
    const FString ConfiguredPath = GeometryManifestPath;
    const FString Path = FPaths::ConvertRelativePathToFull(
        FPaths::IsRelative(GeometryManifestPath)
            ? FPaths::Combine(FPaths::ProjectDir(), GeometryManifestPath)
            : GeometryManifestPath);
    const bool bBuilt = BuildFromGeometryManifest(Path, PreviewMaxLanes, OutError);
    if (bBuilt) GeometryManifestPath = ConfiguredPath;
    return bBuilt;
}

FString ATrafficSumoGeometryActor::GetBuildSummaryJson() const
{
    return FString::Printf(TEXT("{\"total_lane_count\":%d,\"rendered_lane_count\":%d,\"rendered_segment_count\":%d,\"skipped_degenerate_segment_count\":%d,\"junction_count\":%d,\"rendered_tile_count\":%d,\"tile_size_meters\":%.3f,\"texture_repeat_meters\":%.3f,\"local_origin_meters\":{\"x\":%.6f,\"y\":%.6f}}\n"),
        TotalLaneCount, RenderedLaneCount, RenderedSegmentCount, SkippedDegenerateSegmentCount, JunctionCount, RenderedTileCount, TileSizeMeters, TextureRepeatMeters, LocalOriginMeters.X, LocalOriginMeters.Y);
}
