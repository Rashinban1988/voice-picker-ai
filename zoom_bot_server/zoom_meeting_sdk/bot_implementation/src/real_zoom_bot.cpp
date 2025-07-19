#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <fstream>
#include <cmath>
#include <thread>
#include <mutex>
#include <chrono>
#include <jsoncpp/json/json.h>
#include "zoom_sdk.h"
#include "meeting_service_interface.h"
#include "auth_service_interface.h"
#include "zoom_sdk_raw_data_def.h"
#include "rawdata/rawdata_audio_helper_interface.h"
#include "rawdata/zoom_rawdata_api.h"

using namespace ZOOMSDK;

bool g_running = true;
std::mutex g_mtx;
std::string g_audioFilePath;
std::ofstream g_audioFile;
bool g_recording = false;

// WAV file structure
struct WAVHeader {
    char riff[4] = {'R', 'I', 'F', 'F'};
    uint32_t fileSize;
    char wave[4] = {'W', 'A', 'V', 'E'};
    char fmt[4] = {'f', 'm', 't', ' '};
    uint32_t fmtSize = 16;
    uint16_t audioFormat = 1; // PCM
    uint16_t numChannels = 1; // Mono
    uint32_t sampleRate = 16000; // 16kHz
    uint32_t byteRate = 32000; // sampleRate * numChannels * bitsPerSample / 8
    uint16_t blockAlign = 2; // numChannels * bitsPerSample / 8
    uint16_t bitsPerSample = 16;
    char data[4] = {'d', 'a', 't', 'a'};
    uint32_t dataSize = 0;
};

WAVHeader g_wavHeader;
uint32_t g_audioDataSize = 0;

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
}

// Authentication service event handler
class AuthServiceEventHandler : public IAuthServiceEvent {
public:
    void onAuthenticationReturn(AuthResult ret) override {
        std::lock_guard<std::mutex> lock(g_mtx);
        if (ret == AUTHRET_SUCCESS) {
            std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
        } else {
            std::cout << "AUTHENTICATION_FAILED: " << ret << std::endl;
        }
    }
    
    void onLoginRet(LoginStatus ret, ILoginFailInfo* login_fail_info) override {
        // Not used for JWT authentication
    }
    
    void onLogout(LogoutStatus ret) override {
        // Not used
    }
};

// Meeting service event handler
class MeetingServiceEventHandler : public IMeetingServiceEvent {
public:
    void onMeetingStatusChanged(MeetingStatus status, int iResult = 0) override {
        std::lock_guard<std::mutex> lock(g_mtx);
        switch (status) {
            case MEETING_STATUS_CONNECTING:
                std::cout << "MEETING_CONNECTING" << std::endl;
                break;
            case MEETING_STATUS_INMEETING:
                std::cout << "MEETING_JOINED" << std::endl;
                startRecording();
                break;
            case MEETING_STATUS_DISCONNECTING:
                std::cout << "MEETING_DISCONNECTING" << std::endl;
                stopRecording();
                break;
            case MEETING_STATUS_ENDED:
                std::cout << "MEETING_ENDED" << std::endl;
                g_running = false;
                break;
            case MEETING_STATUS_FAILED:
                std::cout << "MEETING_FAILED: " << iResult << std::endl;
                g_running = false;
                break;
        }
    }
    
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override {
        // Handle statistics warnings
    }
    
    void onMeetingParameterNotification(const MeetingParameter* meeting_param) override {
        // Handle meeting parameters
    }
    
    void onSuspendParticipantsActivities() override {
        // Handle suspend activities
    }
    
    void onAICompanionActiveChangeNotification(bool bActive) override {
        // Handle AI companion changes
    }
    
private:
    void startRecording() {
        if (!g_recording) {
            g_recording = true;
            g_audioFile.open(g_audioFilePath, std::ios::binary);
            
            // Write WAV header (we'll update it later)
            g_audioFile.write(reinterpret_cast<const char*>(&g_wavHeader), sizeof(g_wavHeader));
            
            std::cout << "RECORDING_STARTED" << std::endl;
            std::cout << "AUDIO_FILE_CREATED: " << g_audioFilePath << std::endl;
        }
    }
    
    void stopRecording() {
        if (g_recording) {
            g_recording = false;
            
            // Update WAV header with actual file size
            g_wavHeader.fileSize = sizeof(WAVHeader) - 8 + g_audioDataSize;
            g_wavHeader.dataSize = g_audioDataSize;
            
            g_audioFile.seekp(0, std::ios::beg);
            g_audioFile.write(reinterpret_cast<const char*>(&g_wavHeader), sizeof(g_wavHeader));
            g_audioFile.close();
            
            std::cout << "RECORDING_STOPPED" << std::endl;
        }
    }
};

// Audio raw data handler
class AudioRawDataHandler : public IZoomSDKAudioRawDataDelegate {
public:
    void onMixedAudioRawDataReceived(AudioRawData* data) override {
        if (g_recording && data && data->GetBuffer()) {
            std::lock_guard<std::mutex> lock(g_mtx);
            
            // Write audio data to WAV file
            uint32_t dataSize = data->GetBufferLen();
            g_audioFile.write(reinterpret_cast<const char*>(data->GetBuffer()), dataSize);
            g_audioDataSize += dataSize;
            
            // Send heartbeat periodically
            static uint32_t heartbeatCounter = 0;
            if (++heartbeatCounter % 16000 == 0) { // Every ~1 second at 16kHz
                std::cout << "RECORDING_HEARTBEAT" << std::endl;
            }
        }
    }
    
    void onOneWayAudioRawDataReceived(AudioRawData* data, uint32_t user_id) override {
        // Individual participant audio - not used for mixed audio
    }
    
    void onShareAudioRawDataReceived(AudioRawData* data) override {
        // Shared audio - could be used for screen sharing audio
    }
    
    void onOneWayInterpreterAudioRawDataReceived(AudioRawData* data, const zchar_t* pLanguageName) override {
        // Interpreter audio - not used for mixed audio
    }
};

struct Config {
    std::string meetingNumber;
    std::string password;
    std::string userName;
    std::string audioFile;
    std::string sessionId;
    std::string apiKey;
    std::string apiSecret;
};

Config parseConfig(const std::string& configPath) {
    Config config;
    std::ifstream file(configPath);
    Json::Value root;
    Json::Reader reader;
    
    if (!reader.parse(file, root)) {
        throw std::runtime_error("Failed to parse config file");
    }
    
    config.meetingNumber = root["meetingNumber"].asString();
    config.password = root["password"].asString();
    config.userName = root["userName"].asString();
    config.audioFile = root["audioFile"].asString();
    config.sessionId = root["sessionId"].asString();
    
    // Get API credentials from environment
    const char* apiKey = std::getenv("ZOOM_MEETING_SDK_KEY");
    const char* apiSecret = std::getenv("ZOOM_MEETING_SDK_SECRET");
    
    if (!apiKey || !apiSecret) {
        throw std::runtime_error("Zoom SDK credentials not found in environment");
    }
    
    config.apiKey = apiKey;
    config.apiSecret = apiSecret;
    
    return config;
}

int main(int argc, char* argv[]) {
    if (argc < 3 || std::string(argv[1]) != "--config") {
        std::cerr << "Usage: " << argv[0] << " --config <config.json>" << std::endl;
        return 1;
    }
    
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);
    
    try {
        Config config = parseConfig(argv[2]);
        g_audioFilePath = config.audioFile;
        
        std::cout << "STARTING_BOT" << std::endl;
        std::cout << "Meeting: " << config.meetingNumber << std::endl;
        std::cout << "Username: " << config.userName << std::endl;
        
        // Initialize Zoom SDK
        InitParam initParam;
        initParam.pszAppDirPath = "/app/zoom_meeting_sdk";
        initParam.pszLogDirPath = "/app/zoom_meeting_sdk/logs";
        initParam.enableLogByDefault = true;
        initParam.pszLanguageFilePath = "/app/zoom_meeting_sdk/en-US.json";
        
        SDKError initResult = InitSDK(initParam);
        if (initResult != SDKERR_SUCCESS) {
            std::cerr << "ERROR: Failed to initialize SDK: " << initResult << std::endl;
            return 1;
        }
        
        // Create authentication service
        IAuthService* authService = nullptr;
        if (CreateAuthService(&authService) != SDKERR_SUCCESS || !authService) {
            std::cerr << "ERROR: Failed to create auth service" << std::endl;
            CleanUPSDK();
            return 1;
        }
        
        AuthServiceEventHandler authHandler;
        authService->SetEvent(&authHandler);
        
        // Authenticate with JWT
        AuthContext authContext;
        authContext.jwt_token = config.apiKey.c_str(); // JWT token generated by Node.js
        
        AuthResult authResult = authService->AuthorizeSDK(authContext);
        if (authResult != AUTHRET_SUCCESS) {
            std::cerr << "ERROR: Authentication failed: " << authResult << std::endl;
            DestroyAuthService(authService);
            CleanUPSDK();
            return 1;
        }
        
        // Wait for authentication to complete
        std::this_thread::sleep_for(std::chrono::seconds(3));
        
        // Create meeting service
        IMeetingService* meetingService = nullptr;
        if (CreateMeetingService(&meetingService) != SDKERR_SUCCESS || !meetingService) {
            std::cerr << "ERROR: Failed to create meeting service" << std::endl;
            DestroyAuthService(authService);
            CleanUPSDK();
            return 1;
        }
        
        MeetingServiceEventHandler meetingHandler;
        meetingService->SetEvent(&meetingHandler);
        
        // Configure audio raw data
        IZoomSDKAudioRawDataHelper* audioHelper = GetAudioRawdataHelper();
        AudioRawDataHandler audioHandler;
        if (audioHelper) {
            audioHelper->subscribe(&audioHandler, false);
        }
        
        // Join meeting
        JoinParam joinParam;
        joinParam.userType = UT_API_USER;
        joinParam.param.api_param.strMeetingNumber = config.meetingNumber.c_str();
        joinParam.param.api_param.strUserName = config.userName.c_str();
        joinParam.param.api_param.strPassword = config.password.c_str();
        
        MeetingLoginStatus loginStatus = meetingService->Join(joinParam);
        if (loginStatus != MEETING_SUCCESS) {
            std::cerr << "ERROR: Failed to join meeting: " << loginStatus << std::endl;
            DestroyMeetingService(meetingService);
            DestroyAuthService(authService);
            CleanUPSDK();
            return 1;
        }
        
        // Main loop
        while (g_running) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        // Cleanup
        if (audioHelper) {
            audioHelper->unSubscribe();
        }
        
        if (meetingService) {
            meetingService->Leave(LEAVE_MEETING);
            DestroyMeetingService(meetingService);
        }
        
        DestroyAuthService(authService);
        CleanUPSDK();
        
        std::cout << "MEETING_LEFT" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}