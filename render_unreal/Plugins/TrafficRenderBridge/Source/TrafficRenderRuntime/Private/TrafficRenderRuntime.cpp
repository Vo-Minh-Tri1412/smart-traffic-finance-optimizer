#include "Modules/ModuleManager.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "TrafficLiveController.h"

class FTrafficRenderRuntimeModule : public IModuleInterface
{
    FDelegateHandle WorldHandle;
public:
    virtual void StartupModule() override
    {
        int32 Port = 0;
        if (FParse::Value(FCommandLine::Get(), TEXT("TrafficLivePort="), Port))
        {
            WorldHandle = FWorldDelegates::OnPostWorldInitialization.AddLambda(
                [](UWorld* World, const UWorld::InitializationValues)
                {
                    if (World && World->WorldType == EWorldType::Game)
                    {
                        FString ClassPath;
                        UClass* Class = ATrafficLiveController::StaticClass();
                        if (FParse::Value(FCommandLine::Get(),TEXT("TrafficLiveControllerClass="),ClassPath))
                            Class = LoadClass<ATrafficLiveController>(nullptr,*ClassPath);
                        if (Class && Class->IsChildOf(ATrafficLiveController::StaticClass()))
                            World->SpawnActor<ATrafficLiveController>(Class);
                    }
                });
        }
    }
    virtual void ShutdownModule() override
    {
        FWorldDelegates::OnPostWorldInitialization.Remove(WorldHandle);
    }
};
IMPLEMENT_MODULE(FTrafficRenderRuntimeModule, TrafficRenderRuntime)
