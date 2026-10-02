#include "TrafficCityVisualActor.h"

#include "TrafficCityAssetCatalog.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
    struct FResolvedStyle
    {
        const FTrafficCityVisualStyle* Style = nullptr;
        UStaticMesh* Mesh = nullptr;
        UMaterialInterface* Material = nullptr;
    };

    struct FVisualSite
    {
        FString Id;
        FName ZoneType;
        FName Kind;
        double X = 0.0;
        double Y = 0.0;
        double HeadingDegrees = 0.0;
        double FootprintRadiusMeters = 0.0;
    };

    bool Number(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, double& Out)
    {
        return Object->TryGetNumberField(Key, Out) && FMath::IsFinite(Out);
    }

    bool ReadObject(const FString& Path, TSharedPtr<FJsonObject>& Out, FString& OutError)
    {
        FString Text;
        if (!FFileHelper::LoadFileToString(Text, *Path))
        {
            OutError = FString::Printf(TEXT("Cannot read city visual placement manifest: %s"), *Path);
            return false;
        }
        if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Out) || !Out.IsValid())
        {
            OutError = TEXT("City visual placement manifest is not a JSON object");
            return false;
        }
        return true;
    }

    bool ValidStyle(const FTrafficCityVisualStyle& Style)
    {
        return !Style.ZoneType.IsNone() &&
            (Style.Kind == TEXT("building") || Style.Kind == TEXT("landscape")) &&
            FMath::IsFinite(Style.MinHeightMeters) && Style.MinHeightMeters > 0.0f &&
            FMath::IsFinite(Style.MaxHeightMeters) && Style.MaxHeightMeters >= Style.MinHeightMeters &&
            FMath::IsFinite(Style.MaxFootprintDiameterMeters) && Style.MaxFootprintDiameterMeters > 0.0f &&
            FMath::IsFinite(Style.EndCullDistanceMeters) && Style.EndCullDistanceMeters >= 1.0f &&
            Style.EndCullDistanceMeters <= 20000.0f &&
            !Style.AssetSource.IsEmpty() && !Style.License.IsEmpty();
    }
}

ATrafficCityVisualActor::ATrafficCityVisualActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CityVisualRoot"));
    SetRootComponent(SceneRoot);
}

bool ATrafficCityVisualActor::BuildFromPlacementManifest(const FString& InManifestPath, FString& OutError)
{
    if (!AssetCatalog)
    {
        OutError = TEXT("City visual asset catalog is not configured");
        return false;
    }
    if (ExpectedNetSha256.Len() != 64 || ExpectedOverlaySha256.Len() != 64)
    {
        OutError = TEXT("Expected net and overlay SHA-256 values must be configured");
        return false;
    }
    const FString ManifestPath = FPaths::ConvertRelativePathToFull(InManifestPath);
    TSharedPtr<FJsonObject> Manifest;
    if (!ReadObject(ManifestPath, Manifest, OutError)) return false;
    FString Schema, Purpose, CoordinateSystem, NetSha, OverlaySha;
    if (!Manifest->TryGetStringField(TEXT("schema_version"), Schema) || Schema != TEXT("city_visual_placements.v1") ||
        !Manifest->TryGetStringField(TEXT("purpose"), Purpose) || Purpose != TEXT("illustrative_visual_only") ||
        !Manifest->TryGetStringField(TEXT("coordinate_system"), CoordinateSystem) || CoordinateSystem != TEXT("sumo_xy_meters") ||
        !Manifest->TryGetStringField(TEXT("source_net_sha256"), NetSha) || NetSha != ExpectedNetSha256 ||
        !Manifest->TryGetStringField(TEXT("source_overlay_sha256"), OverlaySha) || OverlaySha != ExpectedOverlaySha256)
    {
        OutError = TEXT("City visual placement schema, scope, coordinate system or source hash differs from the retained map");
        return false;
    }
    const TSharedPtr<FJsonObject>* Origin = nullptr;
    double OriginX = 0.0, OriginY = 0.0;
    if (!Manifest->TryGetObjectField(TEXT("local_origin"), Origin) || !Origin || !Origin->IsValid() ||
        !Number(*Origin, TEXT("x"), OriginX) || !Number(*Origin, TEXT("y"), OriginY))
    {
        OutError = TEXT("City visual placement manifest has no finite local origin");
        return false;
    }

    TMap<FName, FResolvedStyle> Styles;
    for (const FTrafficCityVisualStyle& Style : AssetCatalog->Styles)
    {
        if (!ValidStyle(Style) || Styles.Contains(Style.ZoneType))
        {
            OutError = FString::Printf(TEXT("Invalid or duplicate city visual style: %s"), *Style.ZoneType.ToString());
            return false;
        }
        UStaticMesh* Mesh = Style.Mesh.LoadSynchronous();
        UMaterialInterface* Material = Style.MaterialOverride.IsNull()
            ? nullptr : Style.MaterialOverride.LoadSynchronous();
        if (!Mesh || (!Style.MaterialOverride.IsNull() && !Material))
        {
            OutError = FString::Printf(TEXT("Missing mesh or material in city visual style: %s"), *Style.ZoneType.ToString());
            return false;
        }
        const FVector Size = Mesh->GetBoundingBox().GetSize();
        if (Size.X <= 0.0 || Size.Y <= 0.0 || Size.Z <= 0.0)
        {
            OutError = FString::Printf(TEXT("City visual mesh has invalid bounds: %s"), *Style.ZoneType.ToString());
            return false;
        }
        Styles.Add(Style.ZoneType, {&Style, Mesh, Material});
    }

    const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
    double DeclaredCount = 0.0;
    if (!Manifest->TryGetArrayField(TEXT("placements"), Rows) || !Rows ||
        !Number(Manifest, TEXT("placement_count"), DeclaredCount) ||
        DeclaredCount != static_cast<double>(Rows->Num()))
    {
        OutError = TEXT("City visual placement count or array is invalid");
        return false;
    }
    TArray<FVisualSite> Sites;
    Sites.Reserve(Rows->Num());
    TSet<FString> SeenIds;
    for (const TSharedPtr<FJsonValue>& Value : *Rows)
    {
        const TSharedPtr<FJsonObject> Row = Value.IsValid() ? Value->AsObject() : nullptr;
        FString Id, ZoneTypeString, KindString, SourceZoneId, SourceElementId, Basis;
        FVisualSite Site;
        double SourceArea = 0.0, SourceClearance = 0.0;
        if (!Row.IsValid() ||
            !Row->TryGetStringField(TEXT("id"), Id) || Id.IsEmpty() || SeenIds.Contains(Id) ||
            !Row->TryGetStringField(TEXT("source_zone_id"), SourceZoneId) || SourceZoneId.IsEmpty() ||
            !Row->TryGetStringField(TEXT("source_element_id"), SourceElementId) || SourceElementId.IsEmpty() ||
            !Row->TryGetStringField(TEXT("basis"), Basis) || Basis != TEXT("illustrative_site_within_road_clipped_semantic_polygon") ||
            !Row->TryGetStringField(TEXT("zone_type"), ZoneTypeString) || ZoneTypeString.IsEmpty() ||
            !Row->TryGetStringField(TEXT("kind"), KindString) ||
            !Number(Row, TEXT("x_m"), Site.X) || !Number(Row, TEXT("y_m"), Site.Y) ||
            !Number(Row, TEXT("heading_degrees"), Site.HeadingDegrees) ||
            !Number(Row, TEXT("max_footprint_radius_m"), Site.FootprintRadiusMeters) ||
            !Number(Row, TEXT("source_polygon_area_m2"), SourceArea) ||
            !Number(Row, TEXT("source_clearance_m"), SourceClearance) ||
            SourceArea <= 0.0 || SourceClearance <= 0.0 ||
            Site.FootprintRadiusMeters <= 0.0 ||
            Site.FootprintRadiusMeters > SourceClearance * 0.8 + 1e-6 ||
            Site.HeadingDegrees < 0.0 || Site.HeadingDegrees >= 180.0)
        {
            OutError = TEXT("City visual placement row is malformed or duplicated");
            return false;
        }
        Site.Id = Id;
        Site.ZoneType = FName(*ZoneTypeString);
        Site.Kind = FName(*KindString);
        const FResolvedStyle* Resolved = Styles.Find(Site.ZoneType);
        if (!Resolved || Resolved->Style->Kind != Site.Kind)
        {
            OutError = FString::Printf(TEXT("No matching city visual style for zone type %s"), *ZoneTypeString);
            return false;
        }
        SeenIds.Add(Id);
        Sites.Add(MoveTemp(Site));
    }
    if (Sites.IsEmpty())
    {
        OutError = TEXT("City visual placement manifest contains no sites");
        return false;
    }

    for (TObjectPtr<UHierarchicalInstancedStaticMeshComponent>& Component : StyleComponents)
    {
        if (Component) Component->DestroyComponent();
    }
    StyleComponents.Reset();
    RenderedBuildingCount = RenderedLandscapeCount = RenderedStyleCount = 0;
    LocalOriginMeters = FVector2D(OriginX, OriginY);
    PlacementManifestPath = ManifestPath;

    TArray<FName> ZoneTypes;
    Styles.GetKeys(ZoneTypes);
    ZoneTypes.Sort([](const FName& Left, const FName& Right)
    {
        return Left.ToString() < Right.ToString();
    });
    for (const FName& ZoneType : ZoneTypes)
    {
        bool bHasSite = false;
        for (const FVisualSite& Site : Sites)
        {
            if (Site.ZoneType == ZoneType)
            {
                bHasSite = true;
                break;
            }
        }
        if (!bHasSite) continue;
        const FResolvedStyle& Resolved = Styles.FindChecked(ZoneType);
        UHierarchicalInstancedStaticMeshComponent* Component =
            NewObject<UHierarchicalInstancedStaticMeshComponent>(this);
        Component->SetupAttachment(SceneRoot);
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->SetStaticMesh(Resolved.Mesh);
        Component->ComponentTags.Add(ZoneType);
        if (Resolved.Material) Component->SetMaterial(0, Resolved.Material);
        Component->SetCullDistances(0, FMath::RoundToInt(Resolved.Style->EndCullDistanceMeters * 100.0f));
        AddInstanceComponent(Component);
        Component->RegisterComponent();
        const FBox Bounds = Resolved.Mesh->GetBoundingBox();
        const FVector Size = Bounds.GetSize();
        const double HalfFootprintDiagonalCm = FVector2D(Size.X, Size.Y).Size() * 0.5;
        for (const FVisualSite& Site : Sites)
        {
            if (Site.ZoneType != ZoneType) continue;
            const double AllowedRadiusCm = FMath::Min(
                Site.FootprintRadiusMeters * 100.0,
                static_cast<double>(Resolved.Style->MaxFootprintDiameterMeters) * 50.0);
            const double ScaleXY = AllowedRadiusCm / HalfFootprintDiagonalCm;
            const double Fraction = (FCrc::StrCrc32(*Site.Id) % 1000) / 999.0;
            const double HeightMeters = Resolved.Style->MinHeightMeters +
                (Resolved.Style->MaxHeightMeters - Resolved.Style->MinHeightMeters) * Fraction;
            const double ScaleZ = HeightMeters * 100.0 / Size.Z;
            const FVector Location(
                (Site.X - OriginX) * 100.0,
                (Site.Y - OriginY) * 100.0,
                -Bounds.Min.Z * ScaleZ);
            Component->AddInstance(FTransform(
                FRotator(0.0, Site.HeadingDegrees, 0.0),
                Location,
                FVector(ScaleXY, ScaleXY, ScaleZ)));
            if (Site.Kind == TEXT("building")) ++RenderedBuildingCount;
            else ++RenderedLandscapeCount;
        }
        StyleComponents.Add(Component);
        ++RenderedStyleCount;
    }
    return true;
}

bool ATrafficCityVisualActor::RebuildConfiguredPlacements(FString& OutError)
{
    if (PlacementManifestPath.IsEmpty())
    {
        OutError = TEXT("Set a visual placement manifest path before rebuilding city visuals");
        return false;
    }
    const FString ConfiguredPath = PlacementManifestPath;
    const FString Path = FPaths::ConvertRelativePathToFull(
        FPaths::IsRelative(PlacementManifestPath)
            ? FPaths::Combine(FPaths::ProjectDir(), PlacementManifestPath)
            : PlacementManifestPath);
    const bool bBuilt = BuildFromPlacementManifest(Path, OutError);
    if (bBuilt) PlacementManifestPath = ConfiguredPath;
    return bBuilt;
}

FString ATrafficCityVisualActor::GetBuildSummaryJson() const
{
    return FString::Printf(
        TEXT("{\"rendered_building_count\":%d,\"rendered_landscape_count\":%d,\"rendered_style_count\":%d,\"local_origin_meters\":{\"x\":%.6f,\"y\":%.6f}}\n"),
        RenderedBuildingCount, RenderedLandscapeCount, RenderedStyleCount,
        LocalOriginMeters.X, LocalOriginMeters.Y);
}
