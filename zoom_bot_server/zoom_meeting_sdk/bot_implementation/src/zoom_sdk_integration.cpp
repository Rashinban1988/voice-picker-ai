#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <fstream>
#include <vector>
#include <atomic>
#include <mutex>
#include <condition_variable>

// Zoom SDK Headers - Direct inclusion
#include "zoom_sdk.h"
#include "meeting_service_interface.h"
#include "auth_service_interface.h"
#include "meeting_service_components/meeting_audio_interface.h"
#include "rawdata/zoom_rawdata_api.h"
#include "rawdata/rawdata_audio_helper_interface.h"

using namespace ZOOMSDK;

// Global variables
static IAuthService* g_authService = nullptr;
static IMeetingService* g_meetingService = nullptr;
static IZoomSDKAudioRawDataHelper* g_audioHelper = nullptr;
static std::mutex g_sdkMutex;
static std::condition_variable g_sdkCV;
static bool g_isAuthenticated = false;
static bool g_isInMeeting = false;
static std::string g_outputPath;
static std::ofstream g_audioFile;
static std::atomic<bool> g_recording(false);

// WAV Header
struct WAVHeader {
    char riff[4] = {'R', 'I', 'F', 'F'};
    uint32_t fileSize = 36;
    char wave[4] = {'W', 'A', 'V', 'E'};
    char fmt[4] = {'f', 'm', 't', ' '};
    uint32_t fmtSize = 16;
    uint16_t audioFormat = 1;
    uint16_t numChannels = 1;
    uint32_t sampleRate = 16000;
    uint32_t byteRate = 32000;
    uint16_t blockAlign = 2;
    uint16_t bitsPerSample = 16;
    char data[4] = {'d', 'a', 't', 'a'};
    uint32_t dataSize = 0;
};

// Audio Raw Data Delegate
class ZoomAudioRawDataDelegate : public IZoomSDKAudioRawDataDelegate {
private:
    uint32_t totalSamples = 0;
    
public:
    void onMixedAudioRawDataReceived(AudioRawData* data_) override {
        if (!g_recording.load() || !data_ || !g_audioFile.is_open()) return;
        
        char* buffer = data_->GetBuffer();
        unsigned int bufferLen = data_->GetBufferLen();
        
        if (buffer && bufferLen > 0) {
            g_audioFile.write(buffer, bufferLen);
            totalSamples += bufferLen / 2; // 16-bit samples
            
            std::cout << "AUDIO_DATA_RECEIVED: " << bufferLen << " bytes" << std::endl;
        }
    }
    
    void onOneWayAudioRawDataReceived(AudioRawData* data_, uint32_t user_id) override {
        // Individual user audio - not used for now
    }
    
    void onShareAudioRawDataReceived(AudioRawData* data_) override {
        // Share audio - not used for now
    }
    
    void onOneWayInterpreterAudioRawDataReceived(AudioRawData* data_, const zchar_t* pLanguageName) override {
        // Interpreter audio - not used for now
    }
    
    uint32_t getTotalSamples() const { return totalSamples; }
};

// Auth Event Handler
class AuthEventHandler : public IAuthServiceEvent {
public:
    void onAuthenticationReturn(AuthResult ret) override {
        std::lock_guard<std::mutex> lock(g_sdkMutex);
        if (ret == AUTHRET_SUCCESS) {
            g_isAuthenticated = true;
            std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
        } else {
            std::cout << "AUTHENTICATION_FAILED: " << ret << std::endl;
        }
        g_sdkCV.notify_all();
    }
    
    void onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* pAccountInfo, LoginFailReason reason) override {}
    void onLogout() override { g_isAuthenticated = false; }
    void onZoomIdentityExpired() override {}
    void onZoomAuthIdentityExpired() override {}
    void onNotificationServiceStatus(SDKNotificationServiceStatus status, SDKNotificationServiceError error) override {}
};

// Meeting Event Handler
class MeetingEventHandler : public IMeetingServiceEvent {
public:
    void onMeetingStatusChanged(MeetingStatus status, int iResult) override {
        std::lock_guard<std::mutex> lock(g_sdkMutex);
        
        switch (status) {
            case MEETING_STATUS_CONNECTING:
                std::cout << "MEETING_STATUS: Connecting..." << std::endl;
                break;
            case MEETING_STATUS_WAITINGFORHOST:
                std::cout << "MEETING_STATUS: Waiting for host..." << std::endl;
                break;
            case MEETING_STATUS_INMEETING:
                g_isInMeeting = true;
                std::cout << "MEETING_STATUS: In meeting" << std::endl;
                break;
            case MEETING_STATUS_ENDED:
            case MEETING_STATUS_FAILED:
                g_isInMeeting = false;
                std::cout << "MEETING_STATUS: Meeting ended/failed" << std::endl;
                break;
            default:
                std::cout << "MEETING_STATUS: " << status << std::endl;
                break;
        }
        g_sdkCV.notify_all();
    }
    
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override {}
    void onMeetingParameterNotification(const MeetingParameter* meeting_param) override {}
};

// Main SDK functions
extern "C" {

bool InitializeZoomSDK(const char* jwt_token) {
    std::cout << "Initializing Zoom SDK..." << std::endl;
    
    // Initialize SDK with correct parameters
    InitParam initParam;
    initParam.strWebDomain = "https://zoom.us";
    initParam.enableLogByDefault = true;
    initParam.enableGenerateDump = false;
    initParam.emLanguageID = LANGUAGE_English;
    initParam.uiLogFileSize = 5;
    
    SDKError err = InitSDK(initParam);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "InitSDK failed: " << err << std::endl;
        return false;
    }
    
    std::cout << "SDK initialized successfully" << std::endl;
    
    // Create Auth Service
    err = CreateAuthService(&g_authService);
    if (err != SDKERR_SUCCESS || !g_authService) {
        std::cerr << "CreateAuthService failed: " << err << std::endl;
        return false;
    }
    
    // Set Auth Event
    static AuthEventHandler authHandler;
    g_authService->SetEvent(&authHandler);
    
    // Authenticate with JWT
    AuthContext authContext;
    authContext.jwt_token = jwt_token;
    
    err = g_authService->SDKAuth(authContext);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "SDKAuth failed: " << err << std::endl;
        return false;
    }
    
    // Wait for authentication
    {
        std::unique_lock<std::mutex> lock(g_sdkMutex);
        g_sdkCV.wait_for(lock, std::chrono::seconds(10), []{ return g_isAuthenticated; });
    }
    
    if (!g_isAuthenticated) {
        std::cerr << "Authentication timeout" << std::endl;
        return false;
    }
    
    // Create Meeting Service
    err = CreateMeetingService(&g_meetingService);
    if (err != SDKERR_SUCCESS || !g_meetingService) {
        std::cerr << "CreateMeetingService failed: " << err << std::endl;
        return false;
    }
    
    // Set Meeting Event
    static MeetingEventHandler meetingHandler;
    g_meetingService->SetEvent(&meetingHandler);
    
    // Get Audio Raw Data Helper
    if (HasRawdataLicense()) {
        g_audioHelper = GetAudioRawdataHelper();
        if (g_audioHelper) {
            std::cout << "Audio raw data helper obtained" << std::endl;
        }
    }
    
    return true;
}

bool JoinZoomMeeting(const char* meeting_number, const char* password, const char* username) {
    if (!g_meetingService) {
        std::cerr << "Meeting service not initialized" << std::endl;
        return false;
    }
    
    // Convert meeting number to UINT64
    UINT64 meetingNum = 0;
    try {
        meetingNum = std::stoull(meeting_number);
    } catch (...) {
        std::cerr << "Invalid meeting number" << std::endl;
        return false;
    }
    
    std::cout << "Joining meeting: " << meetingNum << std::endl;
    
    // Join meeting parameters - correct structure
    JoinParam joinParam;
    joinParam.userType = SDK_UT_WITHOUT_LOGIN;
    
    // Set meeting parameters correctly
    joinParam.param.withoutloginuserJoin.meetingNumber = meetingNum;
    joinParam.param.withoutloginuserJoin.userName = username;
    joinParam.param.withoutloginuserJoin.psw = password;
    joinParam.param.withoutloginuserJoin.isVideoOff = true;
    joinParam.param.withoutloginuserJoin.isAudioOff = false;
    
    SDKError err = g_meetingService->Join(joinParam);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Join meeting failed: " << err << std::endl;
        return false;
    }
    
    // Wait for meeting to start
    {
        std::unique_lock<std::mutex> lock(g_sdkMutex);
        g_sdkCV.wait_for(lock, std::chrono::seconds(30), []{ return g_isInMeeting; });
    }
    
    return g_isInMeeting;
}

bool StartAudioRecording(const char* output_path) {
    if (!g_audioHelper) {
        std::cerr << "Audio helper not available" << std::endl;
        return false;
    }
    
    g_outputPath = output_path;
    
    // Open audio file
    g_audioFile.open(g_outputPath, std::ios::binary);
    if (!g_audioFile.is_open()) {
        std::cerr << "Failed to open audio file" << std::endl;
        return false;
    }
    
    // Write WAV header
    WAVHeader header;
    g_audioFile.write(reinterpret_cast<const char*>(&header), sizeof(header));
    
    // Subscribe to audio raw data
    static ZoomAudioRawDataDelegate audioDelegate;
    SDKError err = g_audioHelper->subscribe(&audioDelegate, false);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Subscribe to audio failed: " << err << std::endl;
        g_audioFile.close();
        return false;
    }
    
    g_recording.store(true);
    std::cout << "Audio recording started" << std::endl;
    return true;
}

void StopAudioRecording() {
    g_recording.store(false);
    
    if (g_audioHelper) {
        g_audioHelper->unSubscribe();
    }
    
    if (g_audioFile.is_open()) {
        // Update WAV header with correct size
        g_audioFile.seekp(0, std::ios::end);
        uint32_t fileSize = g_audioFile.tellp();
        uint32_t dataSize = fileSize - 44;
        
        g_audioFile.seekp(4);
        fileSize -= 8;
        g_audioFile.write(reinterpret_cast<const char*>(&fileSize), 4);
        
        g_audioFile.seekp(40);
        g_audioFile.write(reinterpret_cast<const char*>(&dataSize), 4);
        
        g_audioFile.close();
    }
    
    std::cout << "Audio recording stopped" << std::endl;
}

void LeaveMeeting() {
    if (g_meetingService && g_isInMeeting) {
        g_meetingService->Leave(LEAVE_MEETING);
    }
}

void CleanupSDK() {
    if (g_meetingService) {
        DestroyMeetingService(g_meetingService);
        g_meetingService = nullptr;
    }
    
    if (g_authService) {
        DestroyAuthService(g_authService);
        g_authService = nullptr;
    }
    
    CleanUPSDK();
}

} // extern "C"