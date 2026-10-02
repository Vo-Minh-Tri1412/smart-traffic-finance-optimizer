#pragma once

#include "CoreMinimal.h"
#include "TrafficRenderTypes.h"

class TRAFFICRENDERRUNTIME_API FTrafficRenderManifestLoader
{
public:
    static bool LoadRenderRunManifest(
        const FString& ManifestPath,
        FTrafficRenderRunManifest& OutManifest,
        FTrafficGeometryManifest& OutGeometry,
        TArray<FString>& OutWarnings,
        FString& OutError);

    static bool LoadGeometryManifest(
        const FString& GeometryManifestPath,
        FTrafficGeometryManifest& OutGeometry,
        TArray<FString>& OutWarnings,
        FString& OutError);

    static FString ResolveArtifactPath(const FString& OwnerPath, const FString& ArtifactPath);
};
