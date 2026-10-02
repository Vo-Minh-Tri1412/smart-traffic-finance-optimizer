#include "TrafficLiveController.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "Engine/AssetManager.h"
#include "Engine/StreamableManager.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "InputCoreTypes.h"
#include "IPAddress.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SocketSubsystem.h"
#include "Sockets.h"
#include "TrafficRenderManifest.h"
#include "TrafficSumoGeometryActor.h"
#include "TrafficVehicleTrace.h"
#include "TrafficReplayVehicleActor.h"
#include "JsonObjectConverter.h"
#include "TrafficUrbanEnvironment.h"
#include "ShaderCompiler.h"

ATrafficLiveController::ATrafficLiveController()
{
    PrimaryActorTick.bCanEverTick = true;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("LiveRoot")));
}

void ATrafficLiveController::BeginPlay()
{
    Super::BeginPlay();
    Port = BridgePort;
    FParse::Value(FCommandLine::Get(), TEXT("TrafficLivePort="), Port);
    BridgePort = Port;
    FString ProfilePath;
    if (FParse::Value(FCommandLine::Get(), TEXT("TrafficLiveProfile="), ProfilePath))
        SceneProfile = TSoftObjectPtr<UTrafficLiveSceneProfile>(FSoftObjectPath(ProfilePath));
    FParse::Value(FCommandLine::Get(), TEXT("TrafficLiveReport="), ReportPath);
    FParse::Value(FCommandLine::Get(), TEXT("TrafficLiveCaptureDir="), CaptureDirectory);
    FParse::Value(FCommandLine::Get(), TEXT("TrafficLiveRecordSeconds="), RecordSeconds);
    bAutoExit = FParse::Param(FCommandLine::Get(), TEXT("TrafficLiveAutoExit"));
    if (Port < 1 || Port > 65535) Fail(TEXT("Invalid live bridge port"));
}

void ATrafficLiveController::Connect()
{
    ISocketSubsystem* Sockets = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    Socket = Sockets->CreateSocket(NAME_Stream, TEXT("SUMO live bridge"), false);
    TSharedRef<FInternetAddr> Address = Sockets->CreateInternetAddr();
    bool Valid = false;
    Address->SetIp(TEXT("127.0.0.1"), Valid);
    Address->SetPort(Port);
    if (!Socket || !Socket->Connect(*Address))
    {
        if (Socket) Sockets->DestroySocket(Socket);
        Socket = nullptr;
        RetryAt = FPlatformTime::Seconds() + 1.0;
        return;
    }
    Socket->SetNonBlocking(true);
    Socket->SetNoDelay(true);
    UE_LOG(LogTemp, Display, TEXT("SUMO_LIVE connected port=%d"), Port);
}

void ATrafficLiveController::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!Failure.IsEmpty()) return;
    if (!Socket && !bComplete && FPlatformTime::Seconds() >= RetryAt) Connect();
    if (Socket) Receive();
    if (bReady) UpdateCamera(DeltaSeconds);
    const double Now = FPlatformTime::Seconds();
    if (bReady && FramesReceived && RecordSeconds > 0 && !CaptureDirectory.IsEmpty() &&
        Now - ReadyWallTime < RecordSeconds && Now >= NextCaptureAt)
    {
        FScreenshotRequest::RequestScreenshot(
            FPaths::Combine(CaptureDirectory, FString::Printf(TEXT("frame_%04d.png"), CaptureCount++)),
            true, false);
        NextCaptureAt = Now + 0.1;
    }
    if (GEngine && (!LoadedScene || LoadedScene->ShowStatus))
    {
        const FString Status = bComplete ? TEXT("finished") : (bReady ? TEXT("live") : TEXT("connecting"));
        GEngine->AddOnScreenDebugMessage(108, 0.1f, FColor::Green,
            FString::Printf(TEXT("SUMO %s | %.1f s | %d vehicles | F: follow | WASD/QE: camera | right mouse: look"),
                *Status, LastFrame.TimeSeconds, Vehicles.Num()));
    }
    if (bReady && !bComplete && FPlatformTime::Seconds() - LastFrameWallTime > 15.0)
        Fail(TEXT("SUMO connection stopped sending frames"));
}

void ATrafficLiveController::Receive()
{
    uint32 Pending = 0;
    for (int32 Chunk = 0; Chunk < 32 && Socket->HasPendingData(Pending) && Pending; ++Chunk)
    {
        uint8 Bytes[65536];
        int32 Read = 0;
        if (!Socket->Recv(Bytes, FMath::Min(Pending, uint32(sizeof(Bytes))), Read) || Read <= 0) break;
        ReceiveBuffer.Append(Bytes, Read);
        if (ReceiveBuffer.Num() > 8 * 1024 * 1024) { Fail(TEXT("Live packet exceeds 8 MiB")); return; }
        int32 Start = 0;
        for (int32 Index = 0; Index < ReceiveBuffer.Num(); ++Index)
        {
            if (ReceiveBuffer[Index] != '\n') continue;
            FUTF8ToTCHAR Text(reinterpret_cast<const ANSICHAR*>(ReceiveBuffer.GetData() + Start), Index - Start);
            HandlePacket(FString(Text.Length(), Text.Get()));
            Start = Index + 1;
            if (!Failure.IsEmpty()) return;
        }
        if (Start) ReceiveBuffer.RemoveAt(0, Start, EAllowShrinking::No);
    }
}

void ATrafficLiveController::HandlePacket(const FString& Line)
{
    TSharedPtr<FJsonObject> Packet;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Line), Packet) || !Packet)
    { Fail(TEXT("Invalid live JSON packet")); return; }
    FString Type;
    if (!Packet->TryGetStringField(TEXT("packet_type"), Type)) { Fail(TEXT("Missing packet_type")); return; }
    if (Type == TEXT("hello"))
    {
        if (bReady || bLoadingAssets) { Fail(TEXT("Duplicate hello")); return; }
        LoadPresentation(Packet);
    }
    else if (Type == TEXT("frame") && bReady && !bComplete) ApplyFrame(Packet);
    else if (Type == TEXT("complete") && bReady)
    {
        bComplete = true;
        WriteReport();
        UE_LOG(LogTemp, Display, TEXT("SUMO_LIVE complete frames=%d pose_changes=%d signal_changes=%d"), FramesReceived, PoseChanges, SignalChanges);
        if (bAutoExit && GetWorld()->GetFirstPlayerController()) GetWorld()->GetFirstPlayerController()->ConsoleCommand(TEXT("quit"));
    }
    else if (Type == TEXT("error")) Fail(Packet->GetStringField(TEXT("message")));
    else Fail(TEXT("Unexpected live packet order"));
}

UStaticMeshComponent* ATrafficLiveController::AddMesh(const FString& Name, UStaticMesh* Asset,
    const FTransform& Pose, UMaterialInterface* Material)
{
    UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(this, MakeUniqueObjectName(this, UStaticMeshComponent::StaticClass(), FName(*Name)));
    Mesh->SetupAttachment(GetRootComponent());
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->SetStaticMesh(Asset);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->SetCastShadow(LoadedScene && LoadedScene->CastShadows);
    if (Material) Mesh->SetMaterial(0, Material);
    Mesh->RegisterComponent();
    Mesh->SetWorldTransform(Pose);
    return Mesh;
}

void ATrafficLiveController::LoadPresentation(const TSharedPtr<FJsonObject>& Packet)
{
    LoadedScene = SceneProfile.LoadSynchronous();
    if (!LoadedScene) { Fail(TEXT("Select a valid SceneProfile Data Asset")); return; }
    Catalog = LoadedScene->Catalog.LoadSynchronous();
    Placement = LoadedScene->Placement.LoadSynchronous();
    if (!Catalog || !Placement) { Fail(TEXT("SceneProfile requires catalog and placement Data Assets")); return; }
    TArray<FSoftObjectPath> Paths;
    auto Add = [&Paths](const auto& Asset) { if (!Asset.IsNull()) Paths.AddUnique(Asset.ToSoftObjectPath()); };
    Add(Catalog->RoadMaterial); Add(Catalog->GroundMesh); Add(Catalog->GroundMaterial);
    Add(Catalog->SignalPoleMesh); Add(Catalog->SignalHousingMesh); Add(Catalog->SignalLensMesh);
    Add(Catalog->SignalRed); Add(Catalog->SignalYellow); Add(Catalog->SignalGreen); Add(Catalog->SignalInactive);
    for (const auto& Vehicle : Catalog->Vehicles)
    {
        for (const auto& Mesh : Vehicle.MeshParts) Add(Mesh);
        Add(Vehicle.MaterialOverride); Add(Vehicle.ActorClass);
    }
    if (!LoadedScene->UrbanEnvironment.IsNull())
    {
        UrbanProfile=LoadedScene->UrbanEnvironment.LoadSynchronous();
        if(!UrbanProfile){Fail(TEXT("Urban profile is unresolved"));return;}
        auto* UrbanCatalog=UrbanProfile->Catalog.LoadSynchronous();
        if(!UrbanCatalog || !UrbanProfile->Placement.LoadSynchronous())
        {Fail(TEXT("Urban catalog/placement is unresolved"));return;}
        for(const auto& Material:UrbanCatalog->FacadeMaterials) Add(Material);
        Add(UrbanCatalog->RoofMaterial);Add(UrbanCatalog->WhiteMarkingMaterial);Add(UrbanCatalog->YellowMarkingMaterial);
        Add(UrbanCatalog->SidewalkMaterial);Add(UrbanCatalog->CurbMaterial);
        for(const auto& Mesh:UrbanCatalog->TreeMeshParts) Add(Mesh);
        Add(UrbanCatalog->TreeMaterialOverride);
    }
    bLoadingAssets = true;
    AssetLoad = UAssetManager::GetStreamableManager().RequestAsyncLoad(Paths,
        FStreamableDelegate::CreateWeakLambda(this,[this,Packet]()
        {
            FString Error;
            if (!InitializeScene(Packet,Error)) { Fail(Error); return; }
            bLoadingAssets = false; bReady = true;
            ReadyWallTime = LastFrameWallTime = FPlatformTime::Seconds();
            NextCaptureAt = ReadyWallTime;
            int32 Sent = 0;
            const ANSICHAR Ready[] = "ready\n";
            if (!Socket || !Socket->Send(reinterpret_cast<const uint8*>(Ready),6,Sent) || Sent != 6)
            { Fail(TEXT("Unable to acknowledge scene readiness")); return; }
            WriteVisualSnapshot(); WriteReport();
        }));
}

bool ATrafficLiveController::InitializeScene(const TSharedPtr<FJsonObject>& Packet, FString& Error)
{
    FString Schema, GeometryPath;
    if (!Packet->TryGetStringField(TEXT("schema_version"),Schema) || Schema != TEXT("sumo_live_bridge.v1") ||
        !Packet->TryGetStringField(TEXT("geometry_manifest"),GeometryPath) || !Packet->TryGetStringField(TEXT("run_id"),RunId))
    { Error = TEXT("Invalid live handshake"); return false; }
    FTrafficGeometryManifest Geometry;
    TArray<FString> Warnings;
    if (!FTrafficRenderManifestLoader::LoadGeometryManifest(GeometryPath,Geometry,Warnings,Error)) return false;
    Transform = FSumoCoordinateTransform(Geometry.LocalOriginMeters);
    RedMaterial = Catalog->SignalRed.Get(); YellowMaterial = Catalog->SignalYellow.Get();
    GreenMaterial = Catalog->SignalGreen.Get(); DarkMaterial = Catalog->SignalInactive.Get();
    if (!RedMaterial || !YellowMaterial || !GreenMaterial || !DarkMaterial || !Catalog->GroundMesh.Get() ||
        !Catalog->SignalPoleMesh.Get() || !Catalog->SignalHousingMesh.Get() || !Catalog->SignalLensMesh.Get() ||
        !Catalog->RoadMaterial.Get() || !Catalog->GroundMaterial.Get() || !Catalog->Vehicles.Num())
    { Error = TEXT("Asset catalog has unresolved critical assets"); return false; }
    if (Placement->PoleDimensionsMeters.GetMin() <= 0 || Placement->HousingDimensionsMeters.GetMin() <= 0 ||
        Placement->LensDimensionsMeters.GetMin() <= 0 || LoadedScene->FieldOfView < 10 || LoadedScene->FieldOfView > 150)
    { Error = TEXT("Visual profile has invalid dimensions or field of view"); return false; }
    Roads = GetWorld()->SpawnActor<ATrafficSumoGeometryActor>();
    Roads->RoadMaterial = Catalog->RoadMaterial.Get();
    if (!Roads->BuildFromGeometryManifest(GeometryPath,0,Error)) return false;
    if(UrbanProfile)
    {
        UrbanActor=GetWorld()->SpawnActor<ATrafficUrbanEnvironment>();UrbanActor->Profile=UrbanProfile;
        if(!UrbanActor->Rebuild(Error)) return false;
    }
    const FVector Min = Transform.SumoPointToUnreal(Geometry.BoundsMin.X,Geometry.BoundsMin.Y,0);
    const FVector Max = Transform.SumoPointToUnreal(Geometry.BoundsMax.X,Geometry.BoundsMax.Y,0);
    const FVector Center = (Min+Max)*0.5;
    const float Margin = Placement->GroundMarginMeters*100;
    const FVector GroundSize(Max.X-Min.X+Margin*2,Max.Y-Min.Y+Margin*2,100);
    auto FitScale = [](UStaticMesh* Mesh,const FVector& SizeCm)
    {
        const FVector Bounds = Mesh->GetBoundingBox().GetSize();
        return FVector(SizeCm.X/FMath::Max(Bounds.X,0.01),SizeCm.Y/FMath::Max(Bounds.Y,0.01),SizeCm.Z/FMath::Max(Bounds.Z,0.01));
    };
    AddMesh(TEXT("Ground"),Catalog->GroundMesh.Get(),
        FTransform(FRotator::ZeroRotator,FVector(Center.X,Center.Y,Placement->GroundTopMeters*100-50),
            FitScale(Catalog->GroundMesh.Get(),GroundSize)),Catalog->GroundMaterial.Get());
    ADirectionalLight* Sun = GetWorld()->SpawnActor<ADirectionalLight>();
    Sun->SetActorRotation(LoadedScene->SunRotation); Sun->GetLightComponent()->SetIntensity(LoadedScene->SunIntensity);
    ASkyLight* Sky = GetWorld()->SpawnActor<ASkyLight>();
    Sky->GetLightComponent()->SetIntensity(LoadedScene->SkyIntensity);
    const TArray<TSharedPtr<FJsonValue>>* Heads = nullptr;
    if (!Packet->TryGetArrayField(TEXT("traffic_light_heads"),Heads)) { Error = TEXT("Missing signal geometry"); return false; }
    for (const auto& Value : *Heads)
    {
        const auto Head = Value->AsObject();
        const FVector Forward(Head->GetNumberField(TEXT("forward_x")),Head->GetNumberField(TEXT("forward_y")),0);
        const FVector Right(Forward.Y,-Forward.X,0);
        const double Offset = Head->GetNumberField(TEXT("lane_width_m"))*0.5 + Placement->RoadsideClearanceMeters +
            Head->GetNumberField(TEXT("lane_head_ordinal"))*Placement->HeadSpacingMeters;
        const FVector Position = Transform.SumoPointToUnreal(Head->GetNumberField(TEXT("x")),Head->GetNumberField(TEXT("y")),Placement->SignalHeightMeters)+Right*Offset*100;
        const FRotator Facing = (-Forward).Rotation();
        SignalTlsIds.Add(Head->GetStringField(TEXT("traffic_light_id")));
        SignalIndices.Add(static_cast<int32>(Head->GetNumberField(TEXT("link_index"))));
        UStaticMesh* Lens = Catalog->SignalLensMesh.Get();
        const FVector LensScale = FitScale(Lens,Placement->LensDimensionsMeters*100);
        RedLenses.Add(AddMesh(TEXT("RedLens"),Lens,FTransform(Facing,Position+FVector(0,0,Placement->LensVerticalSpacingMeters*100),LensScale),DarkMaterial));
        YellowLenses.Add(AddMesh(TEXT("YellowLens"),Lens,FTransform(Facing,Position,LensScale),DarkMaterial));
        GreenLenses.Add(AddMesh(TEXT("GreenLens"),Lens,FTransform(Facing,Position-FVector(0,0,Placement->LensVerticalSpacingMeters*100),LensScale),DarkMaterial));
        SignalMeshes.Add(YellowLenses.Last());
        const FVector PolePosition(Position.X,Position.Y,Placement->PoleDimensionsMeters.Z*50);
        AddMesh(TEXT("SignalPole"),Catalog->SignalPoleMesh.Get(),FTransform(Facing,PolePosition,
            FitScale(Catalog->SignalPoleMesh.Get(),Placement->PoleDimensionsMeters*100)),DarkMaterial);
        AddMesh(TEXT("SignalHousing"),Catalog->SignalHousingMesh.Get(),
            FTransform(Facing,Position+Facing.RotateVector(Placement->HousingOffsetMeters*100),
                FitScale(Catalog->SignalHousingMesh.Get(),Placement->HousingDimensionsMeters*100)),DarkMaterial);
    }
    const auto FocusObject = Packet->GetObjectField(TEXT("camera_focus"));
    Focus = Transform.SumoPointToUnreal(FocusObject->GetNumberField(TEXT("x")),FocusObject->GetNumberField(TEXT("y")),0);
    Camera = GetWorld()->SpawnActor<ACameraActor>();
    Camera->GetCameraComponent()->SetFieldOfView(LoadedScene->FieldOfView);
    FPostProcessSettings& Post = Camera->GetCameraComponent()->PostProcessSettings;
    Post.bOverride_DepthOfFieldEnabled = true; Post.DepthOfFieldEnabled = false;
    Post.bOverride_MotionBlurAmount = true; Post.MotionBlurAmount = 0;
    Post.bOverride_AutoExposureMinBrightness = true; Post.AutoExposureMinBrightness = LoadedScene->FixedExposure;
    Post.bOverride_AutoExposureMaxBrightness = true; Post.AutoExposureMaxBrightness = LoadedScene->FixedExposure;
    Camera->GetCameraComponent()->PostProcessBlendWeight = 1;
    bFollow = LoadedScene->FollowVehicle;
    Camera->SetActorLocation(Focus+LoadedScene->FollowOffsetMeters*100);
    Camera->SetActorRotation((Focus-Camera->GetActorLocation()).Rotation());
    if (auto* Player = GetWorld()->GetFirstPlayerController()) { Player->SetViewTarget(Camera); Player->SetInputMode(FInputModeGameOnly()); }
    if (GShaderCompilingManager) GShaderCompilingManager->FinishAllCompilation();
    UE_LOG(LogTemp,Display,TEXT("SUMO_LIVE ready lanes=%d signals=%d profile=%s"),Roads->RenderedLaneCount,SignalMeshes.Num(),*SceneProfile.ToString());
    return true;
}

void ATrafficLiveController::WriteVisualSnapshot() const
{
    if (ReportPath.IsEmpty()) return;
    TSharedRef<FJsonObject> Snapshot = MakeShared<FJsonObject>();
    Snapshot->SetStringField(TEXT("schema_version"),TEXT("unreal_live_visual_snapshot.v1"));
    Snapshot->SetStringField(TEXT("run_id"),RunId);
    for (const auto* Asset : { static_cast<const UObject*>(LoadedScene),static_cast<const UObject*>(Catalog),static_cast<const UObject*>(Placement) })
    {
        TSharedRef<FJsonObject> Fields = MakeShared<FJsonObject>();
        FJsonObjectConverter::UStructToJsonObject(Asset->GetClass(),Asset,Fields,CPF_Edit,CPF_Transient);
        Snapshot->SetObjectField(Asset->GetClass()->GetName(),Fields);
        Snapshot->SetStringField(Asset->GetClass()->GetName()+TEXT("Path"),Asset->GetPathName());
    }
    if(UrbanProfile) for(const auto* Asset:{static_cast<const UObject*>(UrbanProfile.Get()),
        static_cast<const UObject*>(UrbanProfile->Catalog.Get()),static_cast<const UObject*>(UrbanProfile->Placement.Get())})
    {
        auto Fields=MakeShared<FJsonObject>();
        FJsonObjectConverter::UStructToJsonObject(Asset->GetClass(),Asset,Fields,CPF_Edit,CPF_Transient);
        Snapshot->SetObjectField(Asset->GetClass()->GetName(),Fields);
        Snapshot->SetStringField(Asset->GetClass()->GetName()+TEXT("Path"),Asset->GetPathName());
    }
    FString Json; FJsonSerializer::Serialize(Snapshot,TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*FPaths::Combine(FPaths::GetPath(ReportPath),TEXT("visual_snapshot.json")));
}

void ATrafficLiveController::ApplyFrame(const TSharedPtr<FJsonObject>& Packet)
{
    FString Json;
    FJsonSerializer::Serialize(Packet.ToSharedRef(), TJsonWriterFactory<>::Create(&Json));
    FTrafficVehicleTraceFrame Frame;
    FString Error;
    if (!FTrafficVehicleTrace::ParseFrame(Json, FramesReceived + 1, Frame, Error)) { Fail(Error); return; }
    if (FramesReceived && Frame.TimeSeconds <= LastFrame.TimeSeconds) { Fail(TEXT("SUMO time must advance")); return; }
    TSet<FString> Seen;
    for (const auto& Vehicle : Frame.Vehicles)
    {
        Seen.Add(Vehicle.VehicleId);
        const FTransform Pose = Transform.VehicleCuboidTransform(Vehicle);
        auto& Actor = Vehicles.FindOrAdd(Vehicle.VehicleId);
        if (!Actor)
        {
            const FTrafficVehicleVisualDefinition* Definition = nullptr;
            for (const auto& Candidate : Catalog->Vehicles)
            {
                if (Candidate.VehicleType == Vehicle.VehicleType) { Definition = &Candidate; break; }
                if (Candidate.VehicleType == TEXT("*")) Definition = &Candidate;
            }
            if (!Definition) { Fail(TEXT("No vehicle template matches the SUMO vehicle type")); return; }
            UClass* Class = Definition->ActorClass.IsNull() ? ATrafficReplayVehicleActor::StaticClass() : Definition->ActorClass.Get();
            if (!Class || !Class->IsChildOf(ATrafficReplayVehicleActor::StaticClass())) { Fail(TEXT("Invalid Blueprint vehicle actor class")); return; }
            Actor = GetWorld()->SpawnActor<ATrafficReplayVehicleActor>(Class);
            FString VisualError;
            if (!Actor || !Actor->ConfigureVisual(*Definition,VisualError)) { Fail(VisualError); return; }
            TArray<UStaticMeshComponent*> Components;
            Actor->GetComponents(Components);
            for (UStaticMeshComponent* Component : Components) Component->SetCastShadow(LoadedScene->CastShadows);
        }
        else if (!Actor->GetActorLocation().Equals(Pose.GetLocation(),0.01)) ++PoseChanges;
        Actor->ApplyVehicleState(Vehicle,Pose);
    }
    for (auto It = Vehicles.CreateIterator(); It; ++It)
        if (!Seen.Contains(It.Key())) { It.Value()->Destroy(); It.RemoveCurrent(); }
    const TArray<TSharedPtr<FJsonValue>>* Lights = nullptr;
    if (!Packet->TryGetArrayField(TEXT("traffic_lights"), Lights)) { Fail(TEXT("Frame missing SUMO signal states")); return; }
    TMap<FString, FString> States;
    for (const auto& Value : *Lights)
    {
        const auto Light = Value->AsObject();
        const FString Id = Light->GetStringField(TEXT("traffic_light_id"));
        const FString State = Light->GetStringField(TEXT("state"));
        if (const FString* Previous = PreviousSignalStates.Find(Id); Previous && *Previous != State) ++SignalChanges;
        States.Add(Id, State);
    }
    for (int32 Index = 0; Index < SignalMeshes.Num(); ++Index)
    {
        const FString* State = States.Find(SignalTlsIds[Index]);
        if (!State || !State->IsValidIndex(SignalIndices[Index])) { Fail(TEXT("Signal link has no SUMO state")); return; }
        const TCHAR Color = FChar::ToLower((*State)[SignalIndices[Index]]);
        RedLenses[Index]->SetMaterial(0,(Color == 'r' || Color == 'u') ? RedMaterial.Get() : DarkMaterial.Get());
        YellowLenses[Index]->SetMaterial(0,(Color == 'y' || Color == 'u') ? YellowMaterial.Get() : DarkMaterial.Get());
        GreenLenses[Index]->SetMaterial(0,(Color == 'g' || Color == 's') ? GreenMaterial.Get() : DarkMaterial.Get());
    }
    PreviousSignalStates = MoveTemp(States);
    const TSharedPtr<FJsonObject>* Junction = nullptr;
    bJunctionFocus = Packet->TryGetObjectField(TEXT("camera_junction"),Junction);
    if (bJunctionFocus) JunctionFocus = Transform.SumoPointToUnreal((*Junction)->GetNumberField(TEXT("x")),(*Junction)->GetNumberField(TEXT("y")),0);
    LastFrame = MoveTemp(Frame);
    OnLiveFrameApplied(LastFrame);
    ++FramesReceived;
    MaxVehicles = FMath::Max(MaxVehicles, Vehicles.Num());
    LastFrameWallTime = FPlatformTime::Seconds();
    if (!CaptureDirectory.IsEmpty() && LastFrame.Vehicles.Num() && RecordSeconds <= 0)
    {
        if (!bCaptureFirst && LastFrame.TimeSeconds >= 2)
        { FScreenshotRequest::RequestScreenshot(FPaths::Combine(CaptureDirectory, TEXT("live_02s.png")), false, false); bCaptureFirst = true; }
        if (!bCaptureSecond && LastFrame.TimeSeconds >= 6)
        { FScreenshotRequest::RequestScreenshot(FPaths::Combine(CaptureDirectory, TEXT("live_06s.png")), false, false); bCaptureSecond = true; }
    }
    if (FramesReceived % 10 == 0) WriteReport();
}

void ATrafficLiveController::UpdateCamera(const float DeltaSeconds)
{
    if (!Camera) return;
    APlayerController* Player = GetWorld()->GetFirstPlayerController();
    if (Player)
    {
        if (Player->GetViewTarget() != Camera) Player->SetViewTarget(Camera);
        if (Player->WasInputKeyJustPressed(EKeys::F)) bFollow = !bFollow;
        FVector Move = FVector::ZeroVector;
        if (Player->IsInputKeyDown(EKeys::W)) Move += Camera->GetActorForwardVector();
        if (Player->IsInputKeyDown(EKeys::S)) Move -= Camera->GetActorForwardVector();
        if (Player->IsInputKeyDown(EKeys::D)) Move += Camera->GetActorRightVector();
        if (Player->IsInputKeyDown(EKeys::A)) Move -= Camera->GetActorRightVector();
        if (Player->IsInputKeyDown(EKeys::E)) Move.Z += 1;
        if (Player->IsInputKeyDown(EKeys::Q)) Move.Z -= 1;
        if (!Move.IsNearlyZero()) { bFollow = false; Camera->AddActorWorldOffset(Move * DeltaSeconds * LoadedScene->CameraSpeedMetersPerSecond * 100); }
        if (Player->IsInputKeyDown(EKeys::RightMouseButton))
        {
            bFollow = false;
            float X = 0, Y = 0; Player->GetInputMouseDelta(X,Y);
            FRotator Rotation = Camera->GetActorRotation(); Rotation.Yaw += X; Rotation.Pitch = FMath::Clamp(Rotation.Pitch-Y, -85.0, 85.0);
            Camera->SetActorRotation(Rotation);
        }
    }
    if (bFollow && LastFrame.Vehicles.Num())
    {
        if (!Vehicles.Contains(FollowId)) FollowId = LastFrame.Vehicles[0].VehicleId;
        if (const TObjectPtr<ATrafficReplayVehicleActor>* Vehicle = Vehicles.Find(FollowId))
        {
            Focus = bJunctionFocus ? JunctionFocus : (*Vehicle)->GetActorLocation();
            Camera->SetActorLocation(Focus + (bJunctionFocus ? LoadedScene->JunctionOffsetMeters : LoadedScene->FollowOffsetMeters) * 100);
            Camera->SetActorRotation((Focus-Camera->GetActorLocation()).Rotation());
        }
    }
}

void ATrafficLiveController::WriteReport() const
{
    if (ReportPath.IsEmpty()) return;
    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("schema_version"), TEXT("sumo_unreal_live_quality.v1"));
    Report->SetStringField(TEXT("run_id"), RunId);
    Report->SetStringField(TEXT("status"), !Failure.IsEmpty() ? TEXT("failed") : (bComplete ? TEXT("complete") : (bReady ? TEXT("live") : TEXT("connecting"))));
    Report->SetStringField(TEXT("error"), Failure);
    Report->SetNumberField(TEXT("frames_received"), FramesReceived);
    Report->SetNumberField(TEXT("sumo_time_seconds"), LastFrame.TimeSeconds);
    Report->SetNumberField(TEXT("active_vehicle_count"), Vehicles.Num());
    Report->SetNumberField(TEXT("maximum_vehicle_count"), MaxVehicles);
    Report->SetNumberField(TEXT("vehicle_pose_changes"), PoseChanges);
    Report->SetNumberField(TEXT("traffic_light_state_changes"), SignalChanges);
    Report->SetNumberField(TEXT("traffic_light_head_count"), SignalMeshes.Num());
    Report->SetNumberField(TEXT("rendered_lane_count"), Roads ? Roads->RenderedLaneCount : 0);
    Report->SetStringField(TEXT("scene_profile"),SceneProfile.ToString());
    Report->SetNumberField(TEXT("camera_field_of_view"),Camera ? Camera->GetCameraComponent()->FieldOfView : 0);
    Report->SetNumberField(TEXT("vehicle_template_count"),Catalog ? Catalog->Vehicles.Num() : 0);
    Report->SetNumberField(TEXT("gpu_capture_requests"), CaptureCount);
    if(UrbanActor)
    {
        Report->SetNumberField(TEXT("building_parts"),UrbanActor->BuildingParts);
        Report->SetNumberField(TEXT("lane_marking_segments"),UrbanActor->MarkingSegments);
        Report->SetNumberField(TEXT("sidewalk_segments"),UrbanActor->SidewalkSegments);
        Report->SetNumberField(TEXT("tree_count"),UrbanActor->TreeCount);
    }
    if (LastFrame.Vehicles.Num())
    {
        const FTrafficVehicleState& Vehicle = LastFrame.Vehicles[0];
        TSharedRef<FJsonObject> Sample = MakeShared<FJsonObject>();
        Sample->SetStringField(TEXT("vehicle_id"), Vehicle.VehicleId);
        Sample->SetNumberField(TEXT("sumo_x"), Vehicle.X); Sample->SetNumberField(TEXT("sumo_y"), Vehicle.Y);
        const auto* Mesh = Vehicles.Find(Vehicle.VehicleId);
        if (Mesh && *Mesh)
        {
            const FVector Location = (*Mesh)->GetActorLocation();
            Sample->SetNumberField(TEXT("unreal_x_cm"), Location.X); Sample->SetNumberField(TEXT("unreal_y_cm"), Location.Y);
            Sample->SetNumberField(TEXT("unreal_z_cm"), Location.Z);
            const FVector Size = (*Mesh)->GetVisualDimensionsMeters();
            const FVector Original = (*Mesh)->GetTemplateDimensionsMeters();
            Sample->SetNumberField(TEXT("visual_length_m"),Size.X); Sample->SetNumberField(TEXT("visual_width_m"),Size.Y); Sample->SetNumberField(TEXT("visual_height_m"),Size.Z);
            Sample->SetNumberField(TEXT("template_length_m"),Original.X); Sample->SetNumberField(TEXT("template_width_m"),Original.Y); Sample->SetNumberField(TEXT("template_height_m"),Original.Z);
        }
        Report->SetObjectField(TEXT("sample_vehicle"), Sample);
    }
    FString Json; FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Json));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(ReportPath), true);
    FFileHelper::SaveStringToFile(Json, *ReportPath);
}

void ATrafficLiveController::Fail(const FString& Error)
{
    Failure = Error;
    UE_LOG(LogTemp, Error, TEXT("SUMO_LIVE failed: %s"), *Error);
    if (GEngine) GEngine->AddOnScreenDebugMessage(108, 60, FColor::Red, Error);
    WriteReport();
}

void ATrafficLiveController::EndPlay(const EEndPlayReason::Type Reason)
{
    WriteReport();
    if (Socket) { Socket->Close(); ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket); Socket = nullptr; }
    Super::EndPlay(Reason);
}
