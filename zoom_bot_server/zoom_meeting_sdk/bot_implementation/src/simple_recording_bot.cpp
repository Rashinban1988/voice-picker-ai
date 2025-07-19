#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <fstream>
#include <thread>
#include <chrono>
#include <cstdlib>

// Zoom SDK Headers
#include "zoom_sdk.h"
#include "meeting_service_interface.h"
#include "auth_service_interface.h"
#include "meeting_service_components/meeting_recording_interface.h"

using namespace ZOOMSDK;

bool g_running = true;
bool g_authenticated = false;
bool g_inMeeting = false;

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
}

// Simple Auth Event Handler
class SimpleAuthEventHandler : public IAuthServiceEvent {
public:
    void onAuthenticationReturn(AuthResult ret) override {
        if (ret == AUTHRET_SUCCESS) {
            g_authenticated = true;
            std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
        } else {
            std::cout << "AUTHENTICATION_FAILED: " << ret << std::endl;
        }
    }
    
    void onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* pAccountInfo, LoginFailReason reason) override {}
    void onLogout() override {}
    void onZoomIdentityExpired() override {}
    void onZoomAuthIdentityExpired() override {}
};

// Simple Meeting Event Handler  
class SimpleMeetingEventHandler : public IMeetingServiceEvent {
public:
    void onMeetingStatusChanged(MeetingStatus status, int iResult) override {
        switch (status) {
            case MEETING_STATUS_CONNECTING:
                std::cout << "MEETING_STATUS: Connecting..." << std::endl;
                break;
            case MEETING_STATUS_WAITINGFORHOST:
                std::cout << "MEETING_STATUS: Waiting for host..." << std::endl;
                break;
            case MEETING_STATUS_INMEETING:
                g_inMeeting = true;
                std::cout << "MEETING_STATUS: In meeting" << std::endl;
                break;
            case MEETING_STATUS_ENDED:
            case MEETING_STATUS_FAILED:
                g_inMeeting = false;
                std::cout << "MEETING_STATUS: Meeting ended/failed" << std::endl;
                break;
            default:
                break;
        }
    }
    
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override {}
    void onMeetingParameterNotification(const MeetingParameter* meeting_param) override {}
    void onSuspendParticipantsActivities() override {}
    void onAICompanionActiveChangeNotice(bool bActive) override {}
    void onMeetingTopicChanged(const zchar_t* sTopic) override {}
    void onMeetingFullToWatchLiveStream(const zchar_t* sLiveStreamUrl) override {}
};

// Recording Event Handler
class SimpleRecordingEventHandler : public IMeetingRecordingCtrlEvent {
public:
    void onRecordingStatus(RecordingStatus status) override {
        switch (status) {
            case Recording_Start:
                std::cout << "RECORDING_EVENT: Started" << std::endl;
                break;
            case Recording_Stop:
                std::cout << "RECORDING_EVENT: Stopped" << std::endl;
                break;
            case Recording_Pause:
                std::cout << "RECORDING_EVENT: Paused" << std::endl;
                break;
            case Recording_Connecting:
                std::cout << "RECORDING_EVENT: Connecting..." << std::endl;
                break;
            case Recording_Fail:
                std::cout << "RECORDING_EVENT: Failed" << std::endl;
                break;
            default:
                break;
        }
    }
    
    void onRecordPrivilegeChanged(bool bCanRec) override {
        std::cout << "RECORDING_PRIVILEGE: " << (bCanRec ? "Granted" : "Denied") << std::endl;
    }
    
    void onCustomizedLocalRecordingSourceNotification(ICustomizedLocalRecordingLayoutHelper* layout_helper) override {}
    void onCloudRecordingStatus(RecordingStatus status) override {}
    void onRecordPrivilegeLimited() override {}
    void onLocalRecordingPrivilegeRequestStatus(RequestLocalRecordingStatus status) override {}
    void onStartCloudRecordingRequested() override {}
    void onStartCloudRecordingRequestStatus(RequestStartCloudRecordingStatus status) override {}
    void onRecording2MP4Done(bool bsuccess, int iResult, const zchar_t* szPath) override {
        if (bsuccess) {
            std::cout << "RECORDING_CONVERSION: Success - " << szPath << std::endl;
        } else {
            std::cout << "RECORDING_CONVERSION: Failed" << std::endl;
        }
    }
    void onRecording2MP4Processing(int iPercentage) override {
        std::cout << "RECORDING_CONVERSION: " << iPercentage << "%" << std::endl;
    }
    void onLocalRecordingPrivilegeRequested(IRequestLocalRecordingPrivilegeHandler* handler) override {}
    void onLocalRecordingPrivilegeRequestStatus(LocalRecordingRequestPrivilegeStatus status) override {}
};

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <meeting_number> <password> [username]" << std::endl;
        return 1;
    }
    
    std::string meetingNumber = argv[1];
    std::string password = argv[2];
    std::string userName = argc > 3 ? argv[3] : "Recording Bot";
    
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);
    
    std::cout << "STARTING_BOT" << std::endl;
    
    // Initialize SDK
    InitParam initParam;
    initParam.strWebDomain = "https://zoom.us";
    initParam.enableLogByDefault = true;
    initParam.emLanguageID = LANGUAGE_English;
    
    SDKError err = InitSDK(initParam);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "InitSDK failed: " << err << std::endl;
        return 1;
    }
    
    std::cout << "SDK_INITIALIZED" << std::endl;
    
    // Create Auth Service
    IAuthService* authService = nullptr;
    err = CreateAuthService(&authService);
    if (err != SDKERR_SUCCESS || !authService) {
        std::cerr << "CreateAuthService failed" << std::endl;
        CleanUPSDK();
        return 1;
    }
    
    // Set Auth Event Handler
    SimpleAuthEventHandler authHandler;
    authService->SetEvent(&authHandler);
    
    // Generate JWT token
    const char* sdkKey = std::getenv("ZOOM_MEETING_SDK_KEY");
    const char* sdkSecret = std::getenv("ZOOM_MEETING_SDK_SECRET");
    
    if (!sdkKey || !sdkSecret) {
        std::cerr << "SDK credentials not found in environment" << std::endl;
        CleanUPSDK();
        return 1;
    }
    
    // Note: In production, generate JWT properly
    std::cout << "AUTHENTICATING..." << std::endl;
    
    // For now, use SDK auth (this would need proper JWT in production)
    AuthContext authContext;
    authContext.jwt_token = ""; // JWT token would go here
    
    // Create Meeting Service
    IMeetingService* meetingService = nullptr;
    err = CreateMeetingService(&meetingService);
    if (err != SDKERR_SUCCESS || !meetingService) {
        std::cerr << "CreateMeetingService failed" << std::endl;
        DestroyAuthService(authService);
        CleanUPSDK();
        return 1;
    }
    
    // Set Meeting Event Handler
    SimpleMeetingEventHandler meetingHandler;
    meetingService->SetEvent(&meetingHandler);
    
    // Join Meeting
    std::cout << "JOINING_MEETING: " << meetingNumber << std::endl;
    
    JoinParam joinParam;
    joinParam.userType = SDK_UT_WITHOUT_LOGIN;
    
    // Convert meeting number
    UINT64 meetingNum = 0;
    try {
        meetingNum = std::stoull(meetingNumber);
    } catch (...) {
        std::cerr << "Invalid meeting number" << std::endl;
        DestroyMeetingService(meetingService);
        DestroyAuthService(authService);
        CleanUPSDK();
        return 1;
    }
    
    joinParam.param.withoutloginuserJoin.meetingNumber = meetingNum;
    joinParam.param.withoutloginuserJoin.userName = userName.c_str();
    joinParam.param.withoutloginuserJoin.psw = password.c_str();
    joinParam.param.withoutloginuserJoin.isVideoOff = true;
    joinParam.param.withoutloginuserJoin.isAudioOff = false;
    
    err = meetingService->Join(joinParam);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Join meeting failed: " << err << std::endl;
        DestroyMeetingService(meetingService);
        DestroyAuthService(authService);
        CleanUPSDK();
        return 1;
    }
    
    // Wait for meeting to start
    for (int i = 0; i < 30 && !g_inMeeting; i++) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    
    if (!g_inMeeting) {
        std::cerr << "Failed to join meeting" << std::endl;
        DestroyMeetingService(meetingService);
        DestroyAuthService(authService);
        CleanUPSDK();
        return 1;
    }
    
    std::cout << "MEETING_JOINED" << std::endl;
    
    // Get Recording Controller
    IMeetingRecordingController* recordingCtrl = meetingService->GetMeetingRecordingController();
    if (!recordingCtrl) {
        std::cerr << "Failed to get recording controller" << std::endl;
        meetingService->Leave(LEAVE_MEETING);
        DestroyMeetingService(meetingService);
        DestroyAuthService(authService);
        CleanUPSDK();
        return 1;
    }
    
    // Set Recording Event Handler
    SimpleRecordingEventHandler recordingHandler;
    recordingCtrl->SetEvent(&recordingHandler);
    
    // Check if we can record
    SDKError canRecord = recordingCtrl->CanStartRecording(false, 0); // false = local recording
    if (canRecord != SDKERR_SUCCESS) {
        std::cout << "RECORDING_PERMISSION: Not allowed - " << canRecord << std::endl;
        // Try to request permission
        err = recordingCtrl->RequestLocalRecordingPrivilege();
        if (err == SDKERR_SUCCESS) {
            std::cout << "RECORDING_PERMISSION: Requested" << std::endl;
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
    }
    
    // Start Recording
    std::cout << "STARTING_RECORDING..." << std::endl;
    time_t startTime;
    err = recordingCtrl->StartRecording(startTime);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "StartRecording failed: " << err << std::endl;
    } else {
        std::cout << "RECORDING_STARTED" << std::endl;
    }
    
    // Recording loop
    while (g_running && g_inMeeting) {
        std::cout << "RECORDING_HEARTBEAT" << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(10));
    }
    
    // Stop Recording
    if (g_inMeeting) {
        time_t stopTime;
        err = recordingCtrl->StopRecording(stopTime);
        if (err == SDKERR_SUCCESS) {
            std::cout << "RECORDING_STOPPED" << std::endl;
        }
    }
    
    // Leave Meeting
    meetingService->Leave(LEAVE_MEETING);
    std::cout << "MEETING_LEFT" << std::endl;
    
    // Cleanup
    DestroyMeetingService(meetingService);
    DestroyAuthService(authService);
    CleanUPSDK();
    
    return 0;
}