#include "TrafficReplayController.h"

#include "Engine/World.h"
#include "TrafficReplaySubsystem.h"
#include "TrafficReplayVehicleActor.h"

ATrafficReplayController::ATrafficReplayController()
{
    PrimaryActorTick.bCanEverTick = true;
}

void ATrafficReplayController::BeginPlay()
{
    Super::BeginPlay();
    if (bAutoLoad && !ManifestPath.IsEmpty())
    {
        FString Error;
        if (LoadRenderRun(ManifestPath, 0, Error))
        {
            if (bAutoPlay) Play();
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("Traffic replay failed to load: %s"), *Error);
        }
    }
}

void ATrafficReplayController::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (UTrafficReplaySubsystem* Subsystem = GetReplaySubsystem())
    {
        if (Subsystem->IsPlaying()) Subsystem->AdvanceReplay(DeltaSeconds);
        ApplyCurrentFrame();
    }
}

void ATrafficReplayController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ClearVehicles();
    Super::EndPlay(EndPlayReason);
}

bool ATrafficReplayController::LoadRenderRun(const FString& InManifestPath, const int32 MaxFrames, FString& OutError)
{
    UTrafficReplaySubsystem* Subsystem = GetReplaySubsystem();
    if (!Subsystem || !Subsystem->LoadRenderRun(InManifestPath, MaxFrames, OutError)) return false;
    ManifestPath = InManifestPath;
    ClearVehicles();
    ApplyCurrentFrame();
    return true;
}

void ATrafficReplayController::Play() { if (UTrafficReplaySubsystem* S = GetReplaySubsystem()) S->Play(); }
void ATrafficReplayController::Pause() { if (UTrafficReplaySubsystem* S = GetReplaySubsystem()) S->Pause(); }
void ATrafficReplayController::Seek(const double TimeSeconds) { if (UTrafficReplaySubsystem* S = GetReplaySubsystem()) { S->Seek(TimeSeconds); ApplyCurrentFrame(); } }

bool ATrafficReplayController::ExportQualityReport(const FString& OutputPath, FString& OutError) const
{
    const UTrafficReplaySubsystem* Subsystem = GetReplaySubsystem();
    return Subsystem && Subsystem->WriteQualityReport(OutputPath, OutError);
}

UTrafficReplaySubsystem* ATrafficReplayController::GetReplaySubsystem() const
{
    return GetWorld() ? GetWorld()->GetSubsystem<UTrafficReplaySubsystem>() : nullptr;
}

void ATrafficReplayController::ApplyCurrentFrame()
{
    UTrafficReplaySubsystem* Subsystem = GetReplaySubsystem();
    if (!Subsystem || !GetWorld()) return;
    const FTrafficVehicleTraceFrame Frame = Subsystem->GetCurrentFrame();
    TSet<FString> Seen;
    int32 ActiveCount = 0;
    int32 DroppedCount = 0;
    for (const FTrafficVehicleState& Vehicle : Frame.Vehicles)
    {
        if (ActiveCount >= MaxDebugVehicles || !bSpawnDebugVehicles)
        {
            ++DroppedCount;
            continue;
        }
        TObjectPtr<ATrafficReplayVehicleActor>& Actor = VehicleActors.FindOrAdd(Vehicle.VehicleId);
        if (!Actor)
        {
            FActorSpawnParameters SpawnParameters;
            SpawnParameters.Owner = this;
            SpawnParameters.Name = MakeUniqueObjectName(GetWorld(), ATrafficReplayVehicleActor::StaticClass(), TEXT("ReplayVehicle"));
            Actor = GetWorld()->SpawnActor<ATrafficReplayVehicleActor>(ATrafficReplayVehicleActor::StaticClass(), FTransform::Identity, SpawnParameters);
        }
        if (Actor)
        {
            Seen.Add(Vehicle.VehicleId);
            Actor->ApplyVehicleState(Vehicle, Subsystem->GetCoordinateTransform().VehicleCuboidTransform(Vehicle));
            ++ActiveCount;
        }
        else ++DroppedCount;
    }
    // Bound memory by the current visible set, not all vehicles ever encountered.
    for (auto It = VehicleActors.CreateIterator(); It; ++It)
    {
        if (!Seen.Contains(It.Key()))
        {
            if (It.Value()) It.Value()->Destroy();
            It.RemoveCurrent();
        }
    }
    Subsystem->RecordAppliedFrame(ActiveCount, DroppedCount);
}

void ATrafficReplayController::ClearVehicles()
{
    for (TPair<FString, TObjectPtr<ATrafficReplayVehicleActor>>& Pair : VehicleActors)
    {
        if (Pair.Value) Pair.Value->Destroy();
    }
    VehicleActors.Reset();
}
