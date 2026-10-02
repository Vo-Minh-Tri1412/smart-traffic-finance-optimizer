#include "TrafficUrbanEnvironment.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
    struct FUrbanBuffer
    {
        FVector Origin;
        TArray<FVector> V, N;
        TArray<FVector2D> UV;
        TArray<int32> I;
        void Quad(FVector A,FVector B,FVector C,FVector D,FVector Normal,
                  FVector2D Ua,FVector2D Ub,FVector2D Uc,FVector2D Ud)
        {
            const int32 Base=V.Num();
            V.Append({A-Origin,B-Origin,C-Origin,D-Origin});
            N.Append({Normal,Normal,Normal,Normal}); UV.Append({Ua,Ub,Uc,Ud});
            I.Append({Base,Base+1,Base+2,Base,Base+2,Base+3});
        }
        void Triangle(FVector A,FVector B,FVector C)
        {
            if (FVector::CrossProduct(B-A,C-A).Z<0) Swap(B,C);
            const int32 Base=V.Num(); V.Append({A-Origin,B-Origin,C-Origin});
            N.Append({FVector::UpVector,FVector::UpVector,FVector::UpVector});
            UV.Append({FVector2D(A.X/400,A.Y/400),FVector2D(B.X/400,B.Y/400),FVector2D(C.X/400,C.Y/400)});
            I.Append({Base,Base+1,Base+2});
        }
    };
    FVector2D Point(const TSharedPtr<FJsonValue>& Value)
    {
        const auto& A=Value->AsArray(); return FVector2D(A[0]->AsNumber(),A[1]->AsNumber());
    }
    struct FPath
    {
        TArray<FVector2D> P;
        TArray<double> D;
        double Width=3.2;
        int32 Index=0;
        void Read(const TSharedPtr<FJsonObject>& Lane)
        {
            Width=Lane->GetNumberField(TEXT("width")); Index=Lane->GetIntegerField(TEXT("index"));
            for (const auto& Value:Lane->GetArrayField(TEXT("points"))) P.Add(Point(Value));
            D.Add(0);
            for(int32 i=1;i<P.Num();++i) D.Add(D.Last()+(P[i]-P[i-1]).Size());
        }
        double Length() const { return D.Last(); }
        FVector2D At(double Distance,double RightOffset=0) const
        {
            Distance=FMath::Clamp(Distance,0.0,Length());
            int32 i=1; while(i+1<D.Num() && D[i]<Distance) ++i;
            const FVector2D Forward=(P[i]-P[i-1]).GetSafeNormal();
            const double T=(Distance-D[i-1])/FMath::Max(D[i]-D[i-1],0.000001);
            return FMath::Lerp(P[i-1],P[i],T)+FVector2D(Forward.Y,-Forward.X)*RightOffset;
        }
    };
    struct FExclusion { FVector2D A,B; double HalfWidth; };
    struct FSpatialSafety
    {
        TArray<FExclusion> Segments;
        TMap<FIntPoint,TArray<int32>> RoadGrid,BuildingGrid;
        TArray<FBox2D> Buildings;
        static constexpr double Cell=32;
        template<class Callback> static void Cells(FVector2D Min,FVector2D Max,Callback Fn)
        {
            for(int32 X=FMath::FloorToInt(Min.X/Cell);X<=FMath::FloorToInt(Max.X/Cell);++X)
                for(int32 Y=FMath::FloorToInt(Min.Y/Cell);Y<=FMath::FloorToInt(Max.Y/Cell);++Y) Fn(FIntPoint(X,Y));
        }
        void AddRoad(const TArray<TSharedPtr<FJsonValue>>& A)
        {
            const int32 Id=Segments.Num();
            FExclusion S{{A[0]->AsNumber(),A[1]->AsNumber()},{A[2]->AsNumber(),A[3]->AsNumber()},A[4]->AsNumber()*0.5};
            Segments.Add(S);
            const FVector2D Margin(S.HalfWidth);
            Cells(FVector2D(FMath::Min(S.A.X,S.B.X),FMath::Min(S.A.Y,S.B.Y))-Margin,
                FVector2D(FMath::Max(S.A.X,S.B.X),FMath::Max(S.A.Y,S.B.Y))+Margin,
                [&](FIntPoint Key){RoadGrid.FindOrAdd(Key).Add(Id);});
        }
        void AddBuilding(const TArray<TSharedPtr<FJsonValue>>& A)
        {
            const int32 Id=Buildings.Num();
            FBox2D Box({A[0]->AsNumber(),A[1]->AsNumber()},{A[2]->AsNumber(),A[3]->AsNumber()});
            Buildings.Add(Box);
            Cells(Box.Min,Box.Max,[&](FIntPoint Key){BuildingGrid.FindOrAdd(Key).Add(Id);});
        }
        bool Clear(FVector2D P,double Radius,bool CheckBuildings=true) const
        {
            bool Safe=true; TSet<int32> Checked;
            Cells(P-FVector2D(Radius),P+FVector2D(Radius),[&](FIntPoint Key)
            {
                if(const auto* List=RoadGrid.Find(Key)) for(int32 Id:*List)
                {
                    if(!Safe || Checked.Contains(Id)) continue; Checked.Add(Id);
                    const auto& S=Segments[Id]; const FVector2D Delta=S.B-S.A;
                    const double T=FMath::Clamp(FVector2D::DotProduct(P-S.A,Delta)/FMath::Max(Delta.SizeSquared(),0.000001),0.0,1.0);
                    if((P-(S.A+Delta*T)).Size()<S.HalfWidth+Radius) Safe=false;
                }
                if(CheckBuildings) if(const auto* List=BuildingGrid.Find(Key)) for(int32 Id:*List)
                {
                    const auto& B=Buildings[Id];
                    const double X=FMath::Clamp(P.X,B.Min.X,B.Max.X),Y=FMath::Clamp(P.Y,B.Min.Y,B.Max.Y);
                    if((P-FVector2D(X,Y)).Size()<Radius) Safe=false;
                }
            });
            return Safe;
        }
    };
}

ATrafficUrbanEnvironment::ATrafficUrbanEnvironment()
{
    PrimaryActorTick.bCanEverTick=false;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("UrbanRoot")));
}

bool ATrafficUrbanEnvironment::Rebuild(FString& OutError)
{
    if(!Profile) {OutError=TEXT("Urban scene profile is missing");return false;}
    auto* Catalog=Profile->Catalog.LoadSynchronous();
    auto* Placement=Profile->Placement.LoadSynchronous();
    if(!Catalog || !Placement) {OutError=TEXT("Urban catalog/placement profile is missing");return false;}
    if(Profile->TileSizeMeters<100 || Placement->HeightAssumption.IsEmpty() ||
       Placement->FloorHeightMeters<=0 || Placement->WindowModuleWidthMeters<=0 ||
       Placement->TreeSpacingMeters<3 || Placement->DashLengthMeters<=0 || Placement->DashGapMeters<=0)
    {OutError=TEXT("Urban profile has invalid geometry/assumption settings");return false;}
    FString Path=Placement->GeometrySourcePath;
    if(FPaths::IsRelative(Path)) Path=FPaths::Combine(FPaths::ProjectDir(),Path);
    TArray<uint8> SourceBytes;uint8 Signature[20];
    if(!FFileHelper::LoadFileToArray(SourceBytes,*Path))
    {OutError=TEXT("Urban source geometry cannot be read");return false;}
    FSHA1::HashBuffer(SourceBytes.GetData(),SourceBytes.Num(),Signature);
    if(!BytesToHex(Signature,20).Equals(Placement->GeometrySourceSha1,ESearchCase::IgnoreCase))
    {OutError=TEXT("Urban source geometry checksum does not match the placement profile");return false;}
    FString Text;
    TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*Path) ||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data) || !Data)
    {OutError=TEXT("Urban source geometry cannot be read");return false;}
    if(Data->GetStringField(TEXT("schema_version"))!=TEXT("unreal_urban_geometry.v1") ||
       Data->GetStringField(TEXT("source_net_sha256"))!=Placement->ExpectedNetSha256)
    {OutError=TEXT("Urban geometry does not match the retained SUMO net");return false;}
    const auto Origin=Data->GetObjectField(TEXT("local_origin"));
    const FVector2D LocalOrigin(Origin->GetNumberField(TEXT("x")),Origin->GetNumberField(TEXT("y")));
    auto World=[&](FVector2D P,double Z){return FVector((P.X-LocalOrigin.X)*100,(P.Y-LocalOrigin.Y)*100,Z*100);};
    TArray<UMaterialInterface*> Materials;
    Materials.Add(Catalog->RoofMaterial.LoadSynchronous());
    Materials.Add(Catalog->WhiteMarkingMaterial.LoadSynchronous());
    Materials.Add(Catalog->YellowMarkingMaterial.LoadSynchronous());
    Materials.Add(Catalog->SidewalkMaterial.LoadSynchronous());
    Materials.Add(Catalog->CurbMaterial.LoadSynchronous());
    for(const auto& Ref:Catalog->FacadeMaterials) Materials.Add(Ref.LoadSynchronous());
    if(Materials.Num()<6 || Materials.Contains(nullptr)) {OutError=TEXT("Urban material references are unresolved");return false;}
    for(auto& Tile:MeshTiles) Tile->DestroyComponent(); MeshTiles.Reset();
    for(auto& Component:TreeComponents) Component->DestroyComponent(); TreeComponents.Reset();
    BuildingParts=MarkingSegments=SidewalkSegments=TreeCount=RejectedTreeCount=0; AppliedHeights.Reset();
    TMap<FIntVector,FUrbanBuffer> Buffers;
    auto Buffer=[&](FVector2D P,int32 Material)->FUrbanBuffer&
    {
        FIntVector Key(FMath::FloorToInt((P.X-LocalOrigin.X)/Profile->TileSizeMeters),
            FMath::FloorToInt((P.Y-LocalOrigin.Y)/Profile->TileSizeMeters),Material);
        auto& B=Buffers.FindOrAdd(Key);
        B.Origin=FVector(Key.X*Profile->TileSizeMeters*100,Key.Y*Profile->TileSizeMeters*100,0);
        return B;
    };
    auto Strip=[&](FVector2D A,FVector2D B,double Width,double Z,int32 Material)
    {
        const FVector2D Forward=(B-A).GetSafeNormal(),Side(-Forward.Y*Width*0.5,Forward.X*Width*0.5);
        if((B-A).Size()<0.001) return;
        auto& Mesh=Buffer((A+B)*0.5,Material); const double L=(B-A).Size();
        Mesh.Quad(World(A+Side,Z),World(B+Side,Z),World(B-Side,Z),World(A-Side,Z),FVector::UpVector,
            {0,0},{L,0},{L,Width},{0,Width});
    };
    FSpatialSafety Safety;
    for(const auto& Value:Data->GetArrayField(TEXT("road_exclusion_segments"))) Safety.AddRoad(Value->AsArray());
    for(const auto& Value:Data->GetArrayField(TEXT("buildings"))) Safety.AddBuilding(Value->AsObject()->GetArrayField(TEXT("bounds")));
    if(Profile->Buildings) for(const auto& Value:Data->GetArrayField(TEXT("buildings")))
    {
        const auto Building=Value->AsObject();
        const FString Id=Building->GetStringField(TEXT("id")),Tag=Building->GetStringField(TEXT("building_tag"));
        const FTrafficBuildingHeightRule* Rule=nullptr;
        for(const auto& Candidate:Placement->HeightRules)
        {
            if(Candidate.BuildingTag==Tag){Rule=&Candidate;break;}
            if(Candidate.BuildingTag==TEXT("*")) Rule=&Candidate;
        }
        if(!Rule || Rule->MinHeightMeters<=0 || Rule->MaxHeightMeters<Rule->MinHeightMeters)
        {OutError=TEXT("No valid assumed height rule matches a building");return false;}
        const uint32 Hash=FCrc::StrCrc32(*Id)^uint32(Placement->HeightSeed);
        double Height=FMath::Lerp(double(Rule->MinHeightMeters),double(Rule->MaxHeightMeters),double(Hash%10000)/9999);
        if(const float* Override=Placement->BuildingHeightOverrides.Find(Id)) Height=*Override;
        if(!FMath::IsFinite(Height) || Height<=0 || Height>500) {OutError=TEXT("Building height override is invalid");return false;}
        AppliedHeights.Add(Id,Height);
        const int32 Facade=5+Hash%(Materials.Num()-5);
        for(const auto& RingValue:Building->GetArrayField(TEXT("rings")))
        {
            const auto& Ring=RingValue->AsArray(); double Along=0;
            for(int32 i=0;i+1<Ring.Num();++i)
            {
                const FVector2D A=Point(Ring[i]),B=Point(Ring[i+1]),Delta=B-A;
                const double Length=Delta.Size(); if(Length<0.001) continue;
                const FVector Normal(Delta.Y/Length,-Delta.X/Length,0);
                const double U0=Along/Placement->WindowModuleWidthMeters,U1=(Along+Length)/Placement->WindowModuleWidthMeters;
                auto& Mesh=Buffer((A+B)*0.5,Facade);
                Mesh.Quad(World(A,0),World(B,0),World(B,Height),World(A,Height),Normal,
                    {U0,0},{U1,0},{U1,Height/Placement->FloorHeightMeters},{U0,Height/Placement->FloorHeightMeters});
                Along+=Length;
            }
        }
        for(const auto& Triangle:Building->GetArrayField(TEXT("roof_triangles")))
        {
            const auto& T=Triangle->AsArray(); const FVector2D A=Point(T[0]),B=Point(T[1]),C=Point(T[2]);
            Buffer((A+B+C)/3,0).Triangle(World(A,Height),World(B,Height),World(C,Height));
        }
        ++BuildingParts;
    }
    TSet<FString> Directions;
    for(const auto& Value:Data->GetArrayField(TEXT("roads")))
    {
        const auto Road=Value->AsObject(); Directions.Add(Road->GetStringField(TEXT("from"))+TEXT("|")+Road->GetStringField(TEXT("to")));
    }
    TArray<FVector2D> TreeSites;
    TSet<FIntPoint> TreeCells;
    for(const auto& Value:Data->GetArrayField(TEXT("roads")))
    {
        const auto Road=Value->AsObject(); const auto& Lanes=Road->GetArrayField(TEXT("lanes"));
        const bool Opposite=Directions.Contains(Road->GetStringField(TEXT("to"))+TEXT("|")+Road->GetStringField(TEXT("from")));
        for(int32 LaneIndex=0;LaneIndex<Lanes.Num();++LaneIndex)
        {
            FPath Lane; Lane.Read(Lanes[LaneIndex]->AsObject());
            if(Lane.P.Num()<2 || Lane.Length()<0.01) continue;
            const double Start=FMath::Min(double(Placement->JunctionSetbackMeters),Lane.Length()*0.35),End=Lane.Length()-Start;
            if(Profile->Markings)
            {
                if(LaneIndex+1<Lanes.Num())
                {
                    for(double D=Start;D<End;D+=Placement->DashLengthMeters+Placement->DashGapMeters)
                    {Strip(Lane.At(D,-Lane.Width*0.5),Lane.At(FMath::Min(D+Placement->DashLengthMeters,End),-Lane.Width*0.5),Placement->MarkingWidthMeters,0.012,1);++MarkingSegments;}
                }
                if(LaneIndex==0)
                {
                    for(double D=Start;D<End;D+=4)
                    {Strip(Lane.At(D,Lane.Width*0.5),Lane.At(FMath::Min(D+4,End),Lane.Width*0.5),Placement->MarkingWidthMeters,0.013,1);++MarkingSegments;}
                }
                if(LaneIndex==Lanes.Num()-1)
                {
                    for(double D=Start;D<End;D+=4)
                    {Strip(Lane.At(D,-Lane.Width*0.5),Lane.At(FMath::Min(D+4,End),-Lane.Width*0.5),Placement->MarkingWidthMeters,0.013,Opposite?2:1);++MarkingSegments;}
                }
            }
            if(LaneIndex!=0) continue;
            if(Profile->Sidewalks && Placement->SidewalkWidthMeters>0)
            {
                for(double D=Start;D<End;D+=3)
                {
                    const double Next=FMath::Min(D+3,End),Offset=Lane.Width*0.5+Placement->SidewalkWidthMeters*0.5;
                    const FVector2D A=Lane.At(D,Offset),B=Lane.At(Next,Offset);
                    if(!Safety.Clear((A+B)*0.5,0.3)) continue;
                    Strip(A,B,Placement->SidewalkWidthMeters,Placement->SidewalkHeightMeters,3);
                    Strip(Lane.At(D,Lane.Width*0.5+0.08),Lane.At(Next,Lane.Width*0.5+0.08),0.16,Placement->SidewalkHeightMeters+0.025,4);
                    ++SidewalkSegments;
                }
            }
            if(Profile->Greenery)
            {
                for(double D=Start+Placement->TreeSpacingMeters*0.5;D<End;D+=Placement->TreeSpacingMeters)
                {
                    const FVector2D P=Lane.At(D,Lane.Width*0.5+Placement->SidewalkWidthMeters+Placement->TreeSetbackMeters);
                    const FIntPoint Key(FMath::FloorToInt(P.X/(Placement->TreeCrownRadiusMeters*2+0.5)),FMath::FloorToInt(P.Y/(Placement->TreeCrownRadiusMeters*2+0.5)));
                    if(TreeCells.Contains(Key) || !Safety.Clear(P,Placement->TreeCrownRadiusMeters+0.2))
                    {++RejectedTreeCount;continue;}
                    TreeCells.Add(Key);TreeSites.Add(P);
                }
            }
        }
    }
    TArray<FIntVector> Keys; Buffers.GetKeys(Keys);
    Keys.Sort([](const FIntVector& A,const FIntVector& B){return A.X==B.X?(A.Y==B.Y?A.Z<B.Z:A.Y<B.Y):A.X<B.X;});
    for(const auto& Key:Keys)
    {
        auto& B=Buffers[Key]; if(!B.V.Num()) continue;
        auto* Mesh=NewObject<UProceduralMeshComponent>(this); Mesh->SetupAttachment(GetRootComponent());
        Mesh->SetRelativeLocation(B.Origin);Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Mesh->SetCastShadow(Profile->CastShadows);Mesh->RegisterComponent();
        TArray<FLinearColor> Colors;TArray<FProcMeshTangent> Tangents;
        Mesh->CreateMeshSection_LinearColor(0,B.V,B.I,B.N,B.UV,Colors,Tangents,false);
        Mesh->SetMaterial(0,Materials[Key.Z]);MeshTiles.Add(Mesh);
    }
    if(Profile->Greenery)
    {
        TArray<UStaticMesh*> Parts;FBox Bounds(ForceInit);
        for(const auto& Ref:Catalog->TreeMeshParts)
        {
            auto* Part=Ref.LoadSynchronous();if(!Part){OutError=TEXT("Tree mesh part is unresolved");return false;}
            Parts.Add(Part);Bounds+=Part->GetBoundingBox();
        }
        if(!Parts.Num() || Bounds.GetSize().Z<=0 || Catalog->TreeSource.IsEmpty() || Catalog->TreeLicense.IsEmpty())
        {OutError=TEXT("Tree asset/provenance is incomplete");return false;}
        auto* Override=Catalog->TreeMaterialOverride.IsNull()?nullptr:Catalog->TreeMaterialOverride.LoadSynchronous();
        const double Scale=Placement->TreeHeightMeters/Bounds.GetSize().Z*100;
        for(auto* Part:Parts)
        {
            auto* Instances=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);Instances->SetupAttachment(GetRootComponent());
            Instances->SetStaticMesh(Part);Instances->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Instances->SetCastShadow(Profile->CastShadows);Instances->SetCullDistances(0,Placement->TreeCullDistanceMeters*100);
            if(Override) for(int32 Slot=0;Slot<Instances->GetNumMaterials();++Slot) Instances->SetMaterial(Slot,Override);
            Instances->RegisterComponent();Instances->bAutoRebuildTreeOnInstanceChanges=false;
            for(const auto& Site:TreeSites)
            {
                FVector Position=World(Site,Placement->SidewalkHeightMeters);
                Position.Z-=Bounds.Min.Z*Scale;
                const double Yaw=FCrc::MemCrc32(&Site,sizeof(Site))%360;
                Instances->AddInstance(FTransform(FRotator(0,Yaw,0),Position,FVector(Scale)),false);
            }
            Instances->bAutoRebuildTreeOnInstanceChanges=true;Instances->BuildTreeIfOutdated(true,true);TreeComponents.Add(Instances);
        }
        TreeCount=TreeSites.Num();
    }
    return true;
}

FString ATrafficUrbanEnvironment::GetSummaryJson() const
{
    auto Summary=MakeShared<FJsonObject>();Summary->SetNumberField(TEXT("building_parts"),BuildingParts);
    Summary->SetNumberField(TEXT("marking_segments"),MarkingSegments);Summary->SetNumberField(TEXT("sidewalk_segments"),SidewalkSegments);
    Summary->SetNumberField(TEXT("tree_count"),TreeCount);Summary->SetNumberField(TEXT("rejected_tree_candidates"),RejectedTreeCount);
    Summary->SetNumberField(TEXT("mesh_tile_count"),MeshTiles.Num());
    Summary->SetStringField(TEXT("height_basis"),TEXT("assumed_editable_visual_height"));
    auto Heights=MakeShared<FJsonObject>();for(const auto& Pair:AppliedHeights) Heights->SetNumberField(Pair.Key,Pair.Value);
    Summary->SetObjectField(TEXT("applied_heights_m"),Heights);
    FString Json;FJsonSerializer::Serialize(Summary,TJsonWriterFactory<>::Create(&Json));return Json;
}
