#include "TrafficReplayVehicleActor.h"

#include "Components/StaticMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

ATrafficReplayVehicleActor::ATrafficReplayVehicleActor()
{
    PrimaryActorTick.bCanEverTick = false;
    VehicleMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("VehicleProxy"));
    SetRootComponent(VehicleMesh);
    VehicleMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (CubeMesh.Succeeded()) VehicleMesh->SetStaticMesh(CubeMesh.Object);
}

void ATrafficReplayVehicleActor::ApplyVehicleState(const FTrafficVehicleState& State, const FTransform& CuboidTransform)
{
    VehicleId = State.VehicleId;
    VehicleType = State.VehicleType;
    SetActorTransform(CuboidTransform);
    SetActorHiddenInGame(false);
}
