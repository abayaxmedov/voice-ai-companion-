#include "CompanionDirector.h"

#include "Animation/AnimInstance.h"
#include "CineCameraActor.h"
#include "CompanionBridgePoller.h"
#include "CompanionLipSync.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "Features/IModularFeatures.h"
#include "ILiveLinkClient.h"
#include "Kismet/GameplayStatics.h"
#include "LiveLinkTypes.h"
#include "Roles/LiveLinkAnimationRole.h"
#include "Roles/LiveLinkAnimationTypes.h"
#include "TimerManager.h"

ACompanionDirector::ACompanionDirector()
{
    PrimaryActorTick.bCanEverTick = false;

    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    BridgePoller = CreateDefaultSubobject<UCompanionBridgePoller>(TEXT("BridgePoller"));
}

void ACompanionDirector::BeginPlay()
{
    Super::BeginPlay();

    BridgePoller->OnPlayJobReceived.AddDynamic(this, &ACompanionDirector::HandlePlayJob);
    BridgePoller->OnStateReceived.AddDynamic(this, &ACompanionDirector::HandleState);
    BridgePoller->OnSyncReceived.AddDynamic(this, &ACompanionDirector::HandleSync);
    BridgePoller->OnInterruptReceived.AddDynamic(this, &ACompanionDirector::HandleInterrupt);

    AttachLipSyncToMetaHuman();

    if (bAutoViewTargetToCineCamera)
    {
        GetWorldTimerManager().SetTimer(
            ViewTargetTimerHandle,
            this,
            &ACompanionDirector::TrySetViewTarget,
            0.25f,
            true,
            0.f
        );
    }

    // Idle tiriklik validatsiyasi: 3s isinishdan keyin 0.2s'da bir o'lchaydi.
    GetWorldTimerManager().SetTimer(
        IdleLifeTimerHandle,
        this,
        &ACompanionDirector::ValidateIdleLife,
        0.2f,
        true,
        3.0f
    );
}

void ACompanionDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    GetWorldTimerManager().ClearTimer(ViewTargetTimerHandle);
    GetWorldTimerManager().ClearTimer(FaceValidateTimerHandle);
    GetWorldTimerManager().ClearTimer(IdleLifeTimerHandle);
    Super::EndPlay(EndPlayReason);
}

void ACompanionDirector::AttachLipSyncToMetaHuman()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor->GetName().Contains(MetaHumanActorNameContains))
        {
            continue;
        }
        if (!Actor->FindComponentByClass<USkeletalMeshComponent>())
        {
            continue;
        }

        LipSync = NewObject<UCompanionLipSync>(Actor, TEXT("CompanionLipSync"));
        LipSync->RegisterComponent();
        MetaHumanActor = Actor;
        UE_LOG(LogTemp, Log, TEXT("CompanionDirector: LipSync -> %s"), *Actor->GetName());
        EnableArkitFaceMode(Actor);
        return;
    }

    UE_LOG(LogTemp, Warning,
        TEXT("CompanionDirector: '%s' nomli MetaHuman aktyori topilmadi — lab-sinxron o'chiq"),
        *MetaHumanActorNameContains);
}

void ACompanionDirector::EnableArkitFaceMode(AActor* Actor)
{
    // 1) BP bayroqlari: LiveLinkSetup (Face OnAnimInitialized'ga bog'langan)
    //    keyin qayta ishga tushsa ham ARKit rejimida qolsin.
    for (const TCHAR* PropName : { TEXT("UseARKit"), TEXT("UseLiveLink") })
    {
        if (FBoolProperty* Prop = FindFProperty<FBoolProperty>(Actor->GetClass(), PropName))
        {
            Prop->SetPropertyValue_InContainer(Actor, true);
        }
    }

    // 2) BP'ning o'z LiveLinkSetup funksiyasini chaqiramiz (parametrsiz bo'lsa).
    if (UFunction* Setup = Actor->FindFunction(TEXT("LiveLinkSetup")))
    {
        UE_LOG(LogTemp, Log, TEXT("CompanionDirector: LiveLinkSetup topildi (NumParms=%d)"),
            Setup->NumParms);
        if (Setup->NumParms == 0)
        {
            Actor->ProcessEvent(Setup, nullptr);
        }
    }
    else
    {
        UE_LOG(LogTemp, Log, TEXT("CompanionDirector: LiveLinkSetup funksiyasi topilmadi"));
    }

    // 3) Kafolat: Face mesh anim klassi ABP_MH_LiveLink bo'lsin.
    UClass* LiveLinkAnimClass = LoadClass<UAnimInstance>(nullptr,
        TEXT("/Game/MetaHumans/Common/Animation/ABP_MH_LiveLink.ABP_MH_LiveLink_C"));
    if (!LiveLinkAnimClass)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("CompanionDirector: ABP_MH_LiveLink yuklanmadi — ARKit yuz rejimi o'rnatilmadi"));
        return;
    }

    TInlineComponentArray<USkeletalMeshComponent*> Meshes(Actor);

    // Ko'rinmasa ham anim tick ishlasin: offscreen/stream hali ulanmagan
    // holatlarda ham yuz rigi (va validatsiya) to'xtab qolmasin.
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    }

    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        if (!Mesh->GetName().Contains(TEXT("Face")))
        {
            continue;
        }
        if (Mesh->GetAnimClass() != LiveLinkAnimClass)
        {
            Mesh->SetAnimInstanceClass(LiveLinkAnimClass);
        }

        // Yangi anim instansiyaning subject/gate o'zgaruvchilarini to'ldiramiz.
        if (UAnimInstance* Anim = Mesh->GetAnimInstance())
        {
            // 1) FLiveLinkSubjectName tipidagi barcha xossalar -> yuz subjecti.
            //    (Bosh alohida subject emas — o'sha yuz subjectidan HeadYaw/Pitch/Roll
            //     xossalari BasicRole bilan o'qiladi.)
            const UScriptStruct* SubjectStruct = FLiveLinkSubjectName::StaticStruct();
            for (TFieldIterator<FStructProperty> It(Anim->GetClass()); It; ++It)
            {
                if (It->Struct != SubjectStruct)
                {
                    continue;
                }
                FLiveLinkSubjectName* Value =
                    It->ContainerPtrToValuePtr<FLiveLinkSubjectName>(Anim);
                UE_LOG(LogTemp, Log,
                    TEXT("CompanionDirector: anim subject var '%s': '%s' -> 'LLink_Face_Subj'"),
                    *It->GetName(), *Value->Name.ToString());
                Value->Name = FName(TEXT("LLink_Face_Subj"));
            }

            // 2) Bosh rotatsiyasi gate bool'larini yoqamiz (aks holda ABP
            //    HeadYaw/Pitch/Roll'ni bosh suyagiga qo'llamaydi).
            for (const TCHAR* BoolName : { TEXT("LLink_Face_Head"), TEXT("HeadControlSwitch") })
            {
                if (FBoolProperty* B = FindFProperty<FBoolProperty>(Anim->GetClass(), BoolName))
                {
                    B->SetPropertyValue_InContainer(Anim, true);
                    UE_LOG(LogTemp, Log, TEXT("CompanionDirector: gate '%s' = true"), BoolName);
                }
            }
        }

        FaceMesh = Mesh;
        UE_LOG(LogTemp, Log, TEXT("CompanionDirector: '%s' -> ABP_MH_LiveLink (ARKit rejim)"),
            *Mesh->GetName());
        return;
    }

    UE_LOG(LogTemp, Warning,
        TEXT("CompanionDirector: 'Face' nomli SkeletalMeshComponent topilmadi"));
}

void ACompanionDirector::TrySetViewTarget()
{
    ++ViewTargetAttempts;
    UWorld* World = GetWorld();
    APlayerController* Controller = World ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;

    if (Controller)
    {
        if (AActor* Camera = UGameplayStatics::GetActorOfClass(World, ACineCameraActor::StaticClass()))
        {
            Controller->SetViewTargetWithBlend(Camera, 0.0f);
            UE_LOG(LogTemp, Log, TEXT("CompanionDirector: view target -> %s"), *Camera->GetName());
            GetWorldTimerManager().ClearTimer(ViewTargetTimerHandle);
            return;
        }
    }

    // ~10 soniyadan keyin urinishni to'xtatamiz (kamera yo'q sahna ham yashasin).
    if (ViewTargetAttempts >= 40)
    {
        UE_LOG(LogTemp, Warning, TEXT("CompanionDirector: CineCameraActor/PlayerController topilmadi"));
        GetWorldTimerManager().ClearTimer(ViewTargetTimerHandle);
    }
}

void ACompanionDirector::HandlePlayJob(
    const FString& TurnId,
    const FString& AudioRef,
    const FString& Mood,
    const FString& Behavior,
    const TArray<FCompanionVisemeFrame>& Visemes,
    const FCompanionMouthCurves& MouthCurves)
{
    if (!LipSync)
    {
        return;
    }

    LipSync->StartJob(Visemes, MouthCurves, Mood);
    // Audio Electron tomonida ijro etiladi — hodisa kelgan zahoti boshlaymiz;
    // keyin avatar.sync hodisalari soatni haqiqiy pozitsiyaga tuzatib boradi.
    LipSync->StartPlayback();
    bSyncLoggedThisJob = false;

    if (!bFaceValidated && !FaceValidateTimerHandle.IsValid())
    {
        ProbeOursMax = 0.f;
        ProbeTheirsMax = 0.f;
        ProbeTicks = 0;
        GetWorldTimerManager().SetTimer(
            FaceValidateTimerHandle,
            this,
            &ACompanionDirector::ValidateFaceCurves,
            0.2f,
            true,
            0.5f
        );
    }
}

void ACompanionDirector::ValidateFaceCurves()
{
    if (bFaceValidated || !LipSync || !MetaHumanActor.IsValid())
    {
        GetWorldTimerManager().ClearTimer(FaceValidateTimerHandle);
        return;
    }

    ++ProbeTicks;
    TInlineComponentArray<USkeletalMeshComponent*> Meshes(MetaHumanActor.Get());
    if (LipSync->IsSpeaking())
    {
        ProbeOursMax = FMath::Max(ProbeOursMax, LipSync->GetCurveValue(FName(TEXT("jawOpen"))));
        // Zanjir belgilari: xom subject curve (JawOpen) YOKI PoseAsset chiqargan
        // rig curve (CTRL_expressions_jawOpen) — post-process instansiyada ham.
        static const FName ProbeNames[] = {
            FName(TEXT("JawOpen")), FName(TEXT("jawOpen")),
            FName(TEXT("CTRL_expressions_jawOpen")),
        };
        for (const USkeletalMeshComponent* Mesh : Meshes)
        {
            for (const UAnimInstance* Anim :
                 { Mesh->GetAnimInstance(), Mesh->GetPostProcessInstance() })
            {
                if (!Anim)
                {
                    continue;
                }
                for (const FName& Name : ProbeNames)
                {
                    ProbeTheirsMax = FMath::Max(ProbeTheirsMax, Anim->GetCurveValue(Name));
                }
            }
        }
    }

    // Oyna tugamaguncha yig'averamiz: 10s yoki gapirish tugab yetarli namuna bo'lsa.
    const bool bWindowDone = ProbeTicks >= 50 || (!LipSync->IsSpeaking() && ProbeTicks > 8);
    if (!bWindowDone)
    {
        return;
    }
    GetWorldTimerManager().ClearTimer(FaceValidateTimerHandle);

    const float Ours = ProbeOursMax;
    const float Theirs = ProbeTheirsMax;
    if (Ours < 0.05f)
    {
        UE_LOG(LogTemp, Log,
            TEXT("CompanionDirector: yuz validatsiyasi o'tkazib yuborildi (lab harakati juda kam, jawOpen max=%.3f)"),
            Ours);
        return; // keyingi play'da yana urinamiz
    }

    if (Theirs < 0.005f)
    {
        // Qulflamaymiz — keyingi play'larda yana urinamiz (stale hodisa yoki
        // hali isinmagan zanjir yolg'on-negativ bermasin).
        UE_LOG(LogTemp, Warning,
            TEXT("CompanionDirector: Yuz rigi curve O'QIMAYAPTI (jawOpen lipsync=%.2f, anim=%.3f) — "
                 "LiveLink zanjiri ishlamayapti, docs/FACE_ANIMBP_STEPS.md ga qarang"),
            Ours, Theirs);

        // --- Diagnostika: zanjirning qaysi bo'g'ini uzilganini logga yozamiz. ---
        for (const USkeletalMeshComponent* Mesh : Meshes)
        {
            if (!Mesh->GetName().Contains(TEXT("Face")))
            {
                continue;
            }
            for (UAnimInstance* Anim :
                 { Mesh->GetAnimInstance(), Mesh->GetPostProcessInstance() })
            {
                if (!Anim)
                {
                    continue;
                }
                UE_LOG(LogTemp, Warning, TEXT("  diag: anim instance = %s"),
                    *Anim->GetClass()->GetName());
                // Subject o'zgaruvchilari qiymatini ko'rsatamiz.
                for (TFieldIterator<FStructProperty> It(Anim->GetClass()); It; ++It)
                {
                    if (It->Struct == FLiveLinkSubjectName::StaticStruct())
                    {
                        const FLiveLinkSubjectName* Value =
                            It->ContainerPtrToValuePtr<FLiveLinkSubjectName>(Anim);
                        UE_LOG(LogTemp, Warning, TEXT("  diag:   subject var %s = '%s'"),
                            *It->GetName(), *Value->Name.ToString());
                    }
                }
                // Qaysi curve'lar jonli — uch turda ham sanaymiz.
                for (const EAnimCurveType CurveType :
                     { EAnimCurveType::AttributeCurve, EAnimCurveType::MorphTargetCurve,
                       EAnimCurveType::MaterialCurve })
                {
                    const TMap<FName, float>& Curves = Anim->GetAnimationCurveList(CurveType);
                    int32 NonZero = 0;
                    FString Sample;
                    for (const TPair<FName, float>& Pair : Curves)
                    {
                        if (FMath::Abs(Pair.Value) > 0.01f)
                        {
                            ++NonZero;
                            if (NonZero <= 6)
                            {
                                Sample += FString::Printf(TEXT(" %s=%.2f"),
                                    *Pair.Key.ToString(), Pair.Value);
                            }
                        }
                    }
                    UE_LOG(LogTemp, Warning,
                        TEXT("  diag:   curve turi %d: jami=%d nolmas=%d%s"),
                        static_cast<int32>(CurveType), Curves.Num(), NonZero, *Sample);
                }
            }
        }

        if (IModularFeatures::Get().IsModularFeatureAvailable(ILiveLinkClient::ModularFeatureName))
        {
            ILiveLinkClient& Client = IModularFeatures::Get()
                .GetModularFeature<ILiveLinkClient>(ILiveLinkClient::ModularFeatureName);
            for (const FLiveLinkSubjectKey& Key : Client.GetSubjects(true, true))
            {
                UE_LOG(LogTemp, Warning, TEXT("  diag: subject '%s' enabled=%d"),
                    *Key.SubjectName.ToString(),
                    Client.IsSubjectEnabled(Key, true) ? 1 : 0);
            }
            FLiveLinkSubjectFrameData Snapshot;
            const bool bEval = Client.EvaluateFrame_AnyThread(
                FName(TEXT("LLink_Face_Subj")),
                ULiveLinkAnimationRole::StaticClass(),
                Snapshot);
            int32 PropCount = -1;
            float JawVal = -1.f;
            if (bEval && Snapshot.FrameData.IsValid())
            {
                if (const FLiveLinkBaseFrameData* Base = Snapshot.FrameData.GetBaseData())
                {
                    PropCount = Base->PropertyValues.Num();
                }
                if (const FLiveLinkBaseStaticData* BaseStatic = Snapshot.StaticData.GetBaseData())
                {
                    const int32 Idx = BaseStatic->PropertyNames.Find(FName(TEXT("JawOpen")));
                    if (Idx != INDEX_NONE && Snapshot.FrameData.GetBaseData()->PropertyValues.IsValidIndex(Idx))
                    {
                        JawVal = Snapshot.FrameData.GetBaseData()->PropertyValues[Idx];
                    }
                }
            }
            UE_LOG(LogTemp, Warning,
                TEXT("  diag: EvaluateFrame(anim rol)=%d, props=%d, JawOpen=%.3f"),
                bEval ? 1 : 0, PropCount, JawVal);
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("  diag: LiveLink client YO'Q"));
        }
    }
    else
    {
        bFaceValidated = true;
        UE_LOG(LogTemp, Log,
            TEXT("CompanionDirector: Yuz curve oqimi OK (jawOpen lipsync=%.2f, anim=%.2f)"),
            Ours, Theirs);
    }
}

void ACompanionDirector::ValidateIdleLife()
{
    if (!LipSync || !MetaHumanActor.IsValid())
    {
        GetWorldTimerManager().ClearTimer(IdleLifeTimerHandle);
        return;
    }

    ++IdleProbeTicks;

    // Nigoh curve'lari (biz generatsiya qilamiz).
    float Gaze = 0.f;
    for (const TCHAR* Name : { TEXT("eyeLookOutLeft"), TEXT("eyeLookOutRight"),
                               TEXT("eyeLookInLeft"), TEXT("eyeLookInRight"),
                               TEXT("eyeLookUpLeft"), TEXT("eyeLookDownLeft") })
    {
        Gaze = FMath::Max(Gaze, LipSync->GetCurveValue(FName(Name)));
    }
    IdleGazeMax = FMath::Max(IdleGazeMax, Gaze);

    // Bosh gradusi (biz generatsiya qilamiz).
    const float HeadSubj = FMath::Max3(FMath::Abs(LipSync->GetHeadYaw()),
                                       FMath::Abs(LipSync->GetHeadPitch()),
                                       FMath::Abs(LipSync->GetHeadRoll()));
    IdleHeadSubjMax = FMath::Max(IdleHeadSubjMax, HeadSubj);

    // Face 'head' suyagining haqiqiy og'ishi (ABP HeadYaw/Pitch/Roll natijasi).
    // Dastlabki ~12 tick (yuklanish/poza settling) o'tkazib yuboriladi, so'ng
    // barqaror reference'dan sway radiusi o'lchanadi — bir martalik siljish
    // (settling) natijani ifloslamasligi uchun.
    if (USkeletalMeshComponent* Mesh = FaceMesh.Get())
    {
        if (Mesh->GetBoneIndex(FName("head")) != INDEX_NONE && IdleProbeTicks > 12)
        {
            const FVector Fwd = Mesh->GetBoneQuaternion(
                FName("head"), EBoneSpaces::ComponentSpace).GetForwardVector();
            if (!bIdleHeadBaselineSet)
            {
                IdleHeadBaseline = FQuat(Fwd.Rotation()); // reference yo'nalish
                bIdleHeadBaselineSet = true;
            }
            else
            {
                const FVector Ref = IdleHeadBaseline.GetForwardVector();
                const float AngleDeg = FMath::RadiansToDegrees(
                    FMath::Acos(FMath::Clamp(FVector::DotProduct(Fwd, Ref), -1.f, 1.f)));
                IdleHeadBoneMax = FMath::Max(IdleHeadBoneMax, AngleDeg);
            }
        }
    }

    if (IdleProbeTicks < 55) // ~3s settling + ~8s o'lchov
    {
        return;
    }
    GetWorldTimerManager().ClearTimer(IdleLifeTimerHandle);

    UE_LOG(LogTemp, Log,
        TEXT("CompanionDirector: Idle tiriklik OK (nigoh max=%.2f, saccades=%d, "
             "bosh gradus=%.2f, bosh suyagi og'ishi=%.2f deg)"),
        IdleGazeMax, LipSync->GetSaccadeCount(), IdleHeadSubjMax, IdleHeadBoneMax);

    if (IdleHeadSubjMax > 0.5f && IdleHeadBoneMax < 0.2f)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("CompanionDirector: bosh gradusi generatsiya qilinyapti-yu, bosh suyagi "
                 "qimirlamayapti — HeadYaw/Pitch/Roll ABP'ga yetmayapti (gate/subject)"));
    }
    else if (IdleHeadBoneMax > 15.f)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("CompanionDirector: bosh suyagi og'ishi juda katta (%.1f°) — HeadDegPerUnit "
                 "masshtabi noto'g'ri bo'lishi mumkin (bosh haddan tashqari chayqalyapti)"),
            IdleHeadBoneMax);
    }
}

void ACompanionDirector::HandleState(const FString& State)
{
    if (LipSync)
    {
        LipSync->SetCompanionState(State);
    }
}

void ACompanionDirector::HandleSync(const FString& TurnId, float PositionSeconds)
{
    if (!LipSync || !LipSync->IsSpeaking())
    {
        return;
    }
    LipSync->SyncPlaybackTime(PositionSeconds);
    if (!bSyncLoggedThisJob)
    {
        bSyncLoggedThisJob = true;
        UE_LOG(LogTemp, Log, TEXT("CompanionDirector: audio sync qabul qilindi (%.2fs)"),
            PositionSeconds);
    }
}

void ACompanionDirector::HandleInterrupt(const FString& TurnId, const FString& Reason)
{
    if (LipSync)
    {
        LipSync->StopJob();
    }
}
