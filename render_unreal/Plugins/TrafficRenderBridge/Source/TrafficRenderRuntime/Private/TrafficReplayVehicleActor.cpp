#include "TrafficReplayVehicleActor.h"

#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ATrafficReplayVehicleActor::ATrafficReplayVehicleActor()
{
    PrimaryActorTick.bCanEverTick = false;
    CanonicalRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CanonicalRoot"));
    SetRootComponent(CanonicalRoot);
    VehicleMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VehicleProxy"));
    VehicleMesh->SetupAttachment(CanonicalRoot);
    VehicleMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (CubeMesh.Succeeded()) VehicleMesh->SetStaticMesh(CubeMesh.Object);
}

void ATrafficReplayVehicleActor::ApplyVehicleState(const FTrafficVehicleState& State, const FTransform& CuboidTransform)
{
    VehicleId = State.VehicleId;
    VehicleType = State.VehicleType;
    FTransform Pose = CuboidTransform;
    Pose.SetScale3D(FVector::OneVector);
    SetActorTransform(Pose);
    VehicleMesh->SetRelativeScale3D(CuboidTransform.GetScale3D());
    FitVisual(CuboidTransform.GetScale3D()*100);
    SetActorHiddenInGame(false);
    OnSimulationStateApplied(State);
    // Blueprint may animate visual children, while canonical motion remains SUMO-owned.
    SetActorTransform(Pose);
}

bool ATrafficReplayVehicleActor::ConfigureVisual(const FTrafficVehicleVisualDefinition& Definition, FString& OutError)
{
    TArray<UStaticMesh*> Parts;
    FBox Bounds(ForceInit);
    for (const auto& Reference : Definition.MeshParts)
    {
        UStaticMesh* Mesh = Reference.Get();
        if (!Mesh) { OutError = TEXT("Vehicle mesh is unresolved in the asset catalog"); return false; }
        Parts.Add(Mesh); Bounds += Mesh->GetBoundingBox();
    }
    if (!Parts.Num()) { OutError = TEXT("Vehicle definition has no mesh parts"); return false; }
    float Yaw = 0;
    switch (Definition.ForwardAxis)
    {
        case ETrafficVisualForwardAxis::PositiveY: Yaw = -90; break;
        case ETrafficVisualForwardAxis::NegativeX: Yaw = 180; break;
        case ETrafficVisualForwardAxis::NegativeY: Yaw = 90; break;
        default: break;
    }
    const FRotator Orientation(0,Yaw,0);
    const FBox Oriented = Bounds.TransformBy(FTransform(Orientation));
    const FVector Size = Oriented.GetSize();
    if (Size.GetMin() <= 0 || Size.ContainsNaN()) { OutError = TEXT("Vehicle visual bounds are invalid"); return false; }
    VisualBounds = Oriented;
    VisualOrientation = Orientation;
    bPreserveAspectRatio = Definition.PreserveAspectRatio;
    for (UStaticMeshComponent* Part : VisualParts) Part->DestroyComponent();
    VisualParts.Reset();
    VehicleMesh->SetVisibility(false,false);
    for (UStaticMesh* Mesh : Parts)
    {
        UStaticMeshComponent* Visual = NewObject<UStaticMeshComponent>(this);
        Visual->SetupAttachment(CanonicalRoot);
        Visual->SetMobility(EComponentMobility::Movable);
        Visual->SetStaticMesh(Mesh);
        Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        if (UMaterialInterface* Material = Definition.MaterialOverride.Get())
            for (int32 Slot=0; Slot<Visual->GetNumMaterials(); ++Slot) Visual->SetMaterial(Slot,Material);
        Visual->RegisterComponent();
        VisualParts.Add(Visual);
    }
    return true;
}

void ATrafficReplayVehicleActor::FitVisual(const FVector& CanonicalSizeCm)
{
    if (!VisualParts.Num()) return;
    const FVector Size = VisualBounds.GetSize();
    FVector Scale(CanonicalSizeCm.X/Size.X,CanonicalSizeCm.Y/Size.Y,CanonicalSizeCm.Z/Size.Z);
    if (bPreserveAspectRatio) Scale = FVector(Scale.GetMin());
    const FVector Center = VisualBounds.GetCenter();
    FVector Offset(-Center.X*Scale.X,-Center.Y*Scale.Y,0);
    Offset.Z = -CanonicalSizeCm.Z*0.5 - VisualBounds.Min.Z*Scale.Z;
    const FTransform Local(VisualOrientation,Offset,VisualOrientation.UnrotateVector(Scale).GetAbs());
    for (UStaticMeshComponent* Part : VisualParts) Part->SetRelativeTransform(Local);
}

FVector ATrafficReplayVehicleActor::GetVisualDimensionsMeters() const
{
    FBox Bounds(ForceInit);
    for (const UStaticMeshComponent* Part : VisualParts)
        Bounds += Part->GetStaticMesh()->GetBoundingBox().TransformBy(Part->GetRelativeTransform());
    return Bounds.IsValid ? Bounds.GetSize()/100 : FVector::ZeroVector;
}
