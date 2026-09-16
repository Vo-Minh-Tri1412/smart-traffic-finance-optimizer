#include "TrafficSumoGeometryActor.h"

#include "ProceduralMeshComponent.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "TrafficRenderManifest.h"
#include "TrafficRenderSchemas.h"
#include "XmlFile.h"

namespace
{
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
}

bool ATrafficSumoGeometryActor::BuildFromGeometryManifest(const FString& GeometryManifestPath, const int32 MaxLanes, FString& OutError)
{
    FTrafficGeometryManifest Geometry;
    TArray<FString> Warnings;
    if (!FTrafficRenderManifestLoader::LoadGeometryManifest(GeometryManifestPath, Geometry, Warnings, OutError)) return false;
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
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FLinearColor> Colors;
    TArray<FProcMeshTangent> Tangents;
    TotalLaneCount = RenderedLaneCount = RenderedSegmentCount = JunctionCount = 0;
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
            for (int32 PointIndex = 0; PointIndex + 1 < Shape.Num(); ++PointIndex)
            {
                const FVector2D A = Shape[PointIndex];
                const FVector2D B = Shape[PointIndex + 1];
                const FVector2D Delta = B - A;
                const FVector2D Side = Delta.GetSafeNormal().GetRotated(90.0) * static_cast<float>(Width * 0.5);
                const int32 Base = Vertices.Num();
                Vertices.Add(Transform.SumoPointToUnreal(A.X + Side.X, A.Y + Side.Y));
                Vertices.Add(Transform.SumoPointToUnreal(B.X + Side.X, B.Y + Side.Y));
                Vertices.Add(Transform.SumoPointToUnreal(B.X - Side.X, B.Y - Side.Y));
                Vertices.Add(Transform.SumoPointToUnreal(A.X - Side.X, A.Y - Side.Y));
                Triangles.Add(Base);
                Triangles.Add(Base + 1);
                Triangles.Add(Base + 2);
                Triangles.Add(Base);
                Triangles.Add(Base + 2);
                Triangles.Add(Base + 3);
                for (int32 VertexIndex = 0; VertexIndex < 4; ++VertexIndex)
                {
                    Normals.Add(FVector::UpVector);
                    UVs.Add(FVector2D(VertexIndex == 1 || VertexIndex == 2 ? 1.f : 0.f, VertexIndex >= 2 ? 1.f : 0.f));
                    Colors.Add(FLinearColor::White);
                    Tangents.Add(FProcMeshTangent(FVector::ForwardVector, false));
                }
                ++RenderedSegmentCount;
            }
            ++RenderedLaneCount;
        }
    }
    RoadMesh->ClearAllMeshSections();
    if (Vertices.Num() > 0) RoadMesh->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
    return true;
}

FString ATrafficSumoGeometryActor::GetBuildSummaryJson() const
{
    return FString::Printf(TEXT("{\"total_lane_count\":%d,\"rendered_lane_count\":%d,\"rendered_segment_count\":%d,\"junction_count\":%d,\"local_origin_meters\":{\"x\":%.6f,\"y\":%.6f}}\n"),
        TotalLaneCount, RenderedLaneCount, RenderedSegmentCount, JunctionCount, LocalOriginMeters.X, LocalOriginMeters.Y);
}
