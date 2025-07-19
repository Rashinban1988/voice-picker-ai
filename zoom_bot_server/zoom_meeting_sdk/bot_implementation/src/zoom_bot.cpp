#include "zoom_bot.h"
#include <iostream>
#include <cstdlib>
#include <thread>
#include <chrono>

// Zoom SDK includes
#include "zoom_sdk.h"
#include "meeting_service_interface.h"
#include "auth_service_interface.h"
#include "meeting_service_components/meeting_audio_interface.h"
#include "rawdata/zoom_rawdata_api.h"

using namespace ZOOMSDK;

// Audio data callback implementation
class AudioRawDataHelper : public IZoomSDKAudioRawDataDelegate {
public:
    AudioRawDataHelper(ZoomBot* bot) : bot_(bot) {}
    
    void onMixedAudioRawDataReceived(AudioRawData* data_) override {
        if (data_ && data_->GetBuffer() && data_->GetBufferLen() > 0) {
            bot_->onAudioDataReceived(
                reinterpret_cast<const char*>(data_->GetBuffer()),
                data_->GetBufferLen()
            );
        }
    }
    
    void onOneWayAudioRawDataReceived(AudioRawData* data_, uint32_t node_id) override {
        // We're primarily interested in mixed audio
    }
    
private:
    ZoomBot* bot_;
};

// Meeting event callback implementation
class MeetingEventHandler : public IMeetingServiceEvent {
public:
    MeetingEventHandler(ZoomBot* bot) : bot_(bot) {}
    
    void onMeetingStatusChanged(MEETING_STATUS status, int iResult = 0) override {
        switch (status) {
            case MEETING_STATUS_INMEETING:
                std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
                bot_->onMeetingJoined();
                break;
            case MEETING_STATUS_ENDED:
            case MEETING_STATUS_FAILED:
                bot_->onMeetingLeft();
                break;
            default:
                break;
        }
    }
    
    void onMeetingParameterNotification(const MeetingParameter* meeting_param) override {}
    void onSuspendParticipantsActivities() override {}
    void onAICompanionActiveChangeNotice(bool bActive) override {}
    void onParticipantsShareStateChanged(ShareInfo& shareInfo) override {}
    void onMeetingDeviceListChanged(const ZOOM_DEVICE_TYPE& deviceType) override {}
    
private:
    ZoomBot* bot_;
};

// Auth event callback implementation
class AuthEventHandler : public IAuthServiceEvent {
public:
    AuthEventHandler(ZoomBot* bot) : bot_(bot) {}
    
    void onAuthenticationReturn(LOGINRET ret) override {
        if (ret == LOGINRET_SUCCESS) {
            std::cout << "SDK Authentication successful" << std::endl;
        } else {
            std::cerr << "SDK Authentication failed: " << ret << std::endl;
        }
    }
    
    void onLoginRet(LOGINRET ret, ILoginInfo* login_info) override {}
    void onLogout() override {}
    void onZoomIdentityExpired() override {}
    void onZoomAuthIdentityExpired() override {}
    
private:
    ZoomBot* bot_;
};

ZoomBot::ZoomBot(const ConfigParser& config)
    : config_(config)
    , sdk_(nullptr)
    , meetingService_(nullptr)
    , authService_(nullptr)
    , isInitialized_(false)
    , isMeetingJoined_(false)
    , isRecording_(false) {
    
    audioRecorder_ = std::make_unique<AudioRecorder>(config_.getAudioFile());
}

ZoomBot::~ZoomBot() {
    cleanup();
}

bool ZoomBot::initialize() {
    if (isInitialized_) {
        return true;
    }
    
    // Initialize Zoom SDK
    InitParam init_param;
    init_param.strAppDirPath = "./";
    
    SDKError ret = InitSDK(init_param);
    if (ret != SDKERROR_SUCCESS) {
        std::cerr << "Failed to initialize SDK: " << ret << std::endl;
        return false;
    }
    
    sdk_ = GetZoomSDK();
    if (!sdk_) {
        std::cerr << "Failed to get SDK instance" << std::endl;
        return false;
    }
    
    // Get services
    authService_ = sdk_->GetAuthService();
    meetingService_ = sdk_->GetMeetingService();
    
    if (!authService_ || !meetingService_) {
        std::cerr << "Failed to get SDK services" << std::endl;
        return false;
    }
    
    // Set up event handlers
    static AuthEventHandler authHandler(this);
    static MeetingEventHandler meetingHandler(this);
    
    authService_->SetEvent(&authHandler);
    meetingService_->SetEvent(&meetingHandler);
    
    // Authenticate SDK
    if (!authenticateSDK()) {
        return false;
    }
    
    // Initialize audio recorder
    if (!audioRecorder_->initialize()) {
        std::cerr << "Failed to initialize audio recorder" << std::endl;
        return false;
    }
    
    isInitialized_ = true;
    return true;
}

bool ZoomBot::authenticateSDK() {
    AuthParam auth_param;
    auth_param.appKey = config_.getSDKKey().c_str();
    auth_param.appSecret = config_.getSDKSecret().c_str();
    
    SDKError ret = authService_->SDKAuth(auth_param);
    if (ret != SDKERROR_SUCCESS) {
        std::cerr << "SDK auth failed: " << ret << std::endl;
        return false;
    }
    
    // Wait for authentication result
    for (int i = 0; i < 30; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        // In a real implementation, you'd check the auth status here
    }
    
    return true;
}

bool ZoomBot::joinMeeting() {
    if (!isInitialized_ || isMeetingJoined_) {
        return false;
    }
    
    JoinParam join_param;
    join_param.userType = SDK_UT_WITHOUT_LOGIN;
    
    JoinParam4WithoutLogin& param = join_param.param.param4WithoutLogin;
    param.meetingNumber = std::stoull(config_.getMeetingNumber());
    param.userName = config_.getUserName().c_str();
    param.psw = config_.getPassword().c_str();
    param.hDirectShareAppWnd = nullptr;
    param.toke4enfrocelogin = nullptr;
    param.participantId = nullptr;
    param.webinarToken = nullptr;
    param.isVideoOff = true;  // Join with video off
    param.isAudioOff = false; // Join with audio on
    
    SDKError ret = meetingService_->Join(join_param);
    if (ret != SDKERROR_SUCCESS) {
        std::cerr << "Failed to join meeting: " << ret << std::endl;
        return false;
    }
    
    // Wait for meeting join
    for (int i = 0; i < 100; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        if (isMeetingJoined_) {
            break;
        }
    }
    
    return isMeetingJoined_;
}

bool ZoomBot::startRecording() {
    if (!isMeetingJoined_ || isRecording_) {
        return false;
    }
    
    // Start audio recorder
    if (!audioRecorder_->startRecording()) {
        std::cerr << "Failed to start audio recorder" << std::endl;
        return false;
    }
    
    // Set up audio raw data
    IZoomSDKAudioRawDataFactory* audio_factory = GetAudioRawdataFactory();
    if (!audio_factory) {
        std::cerr << "Failed to get audio factory" << std::endl;
        return false;
    }
    
    IZoomSDKAudioRawDataHelper* audio_helper = audio_factory->GetAudioRawDataHelper();
    if (!audio_helper) {
        std::cerr << "Failed to get audio helper" << std::endl;
        return false;
    }
    
    static AudioRawDataHelper audioDataHandler(this);
    audio_helper->subscribe(&audioDataHandler);
    
    isRecording_ = true;
    return true;
}

bool ZoomBot::stopRecording() {
    if (!isRecording_) {
        return true;
    }
    
    // Unsubscribe from audio data
    IZoomSDKAudioRawDataFactory* audio_factory = GetAudioRawdataFactory();
    if (audio_factory) {
        IZoomSDKAudioRawDataHelper* audio_helper = audio_factory->GetAudioRawDataHelper();
        if (audio_helper) {
            audio_helper->unSubscribe();
        }
    }
    
    // Stop audio recorder
    audioRecorder_->stopRecording();
    
    // Leave meeting
    if (meetingService_ && isMeetingJoined_) {
        meetingService_->Leave(LEAVE_MEETING);
    }
    
    isRecording_ = false;
    isMeetingJoined_ = false;
    
    return true;
}

void ZoomBot::processEvents() {
    // Process SDK events - in a real implementation this would handle SDK message pumping
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}

void ZoomBot::cleanup() {
    if (isRecording_) {
        stopRecording();
    }
    
    if (sdk_) {
        CleanupSDK();
        sdk_ = nullptr;
    }
    
    isInitialized_ = false;
}

void ZoomBot::onMeetingJoined() {
    isMeetingJoined_ = true;
}

void ZoomBot::onMeetingLeft() {
    isMeetingJoined_ = false;
    isRecording_ = false;
}

void ZoomBot::onAudioDataReceived(const char* data, int length) {
    if (isRecording_ && audioRecorder_) {
        audioRecorder_->writeAudioData(data, length);
    }
}