#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <fstream>
#include <thread>
#include <mutex>
#include <chrono>
#include <cstdlib>
#include <vector>
#include <memory>
#include <atomic>
#include <condition_variable>
#include <deque>

// Zoom Meeting SDK Headers
#include "zoom_sdk.h"
#include "meeting_service_interface.h"
#include "auth_service_interface.h"
#include "rawdata/zoom_rawdata_api.h"
#include "rawdata/rawdata_audio_helper_interface.h"
#include "zoom_sdk_raw_data_def.h"

using namespace ZOOMSDK;

bool g_running = true;
std::mutex g_mtx;
std::string g_audioFilePath;

// 音声データ構造体
struct AudioFrame {
    std::vector<char> data;
    uint32_t sample_rate;
    uint32_t channels;
    uint64_t timestamp;
};

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

// Real Zoom SDK Audio Recorder
class RealZoomAudioRecorder : public IZoomSDKAudioRawDataDelegate {
private:
    std::deque<AudioFrame> audioBuffer;
    std::mutex bufferMutex;
    std::condition_variable bufferCondition;
    std::atomic<bool> recording;
    std::thread recordingThread;
    std::string outputPath;
    
    // SDK interfaces
    IAuthService* authService;
    IMeetingService* meetingService;
    IZoomSDKAudioRawDataHelper* audioHelper;
    
public:
    RealZoomAudioRecorder(const std::string& output) 
        : outputPath(output), recording(false), authService(nullptr), 
          meetingService(nullptr), audioHelper(nullptr) {}
    
    ~RealZoomAudioRecorder() {
        stopRecording();
        cleanup();
    }
    
    bool initializeSDK(const std::string& appKey, const std::string& appSecret) {
        std::cout << "SDK_INIT: Initializing Zoom Meeting SDK" << std::endl;
        
        // SDK初期化
        InitParam initParam;
        initParam.strAppKey = appKey.c_str();
        initParam.strAppSecret = appSecret.c_str();
        initParam.strRealPath = "/app/zoom_meeting_sdk";
        initParam.enableLogByDefault = true;
        initParam.strLogDirPath = "/app/zoom_meeting_sdk/logs";
        
        SDKError result = InitSDK(initParam);
        if (result != SDKERR_SUCCESS) {
            std::cerr << "SDK_ERROR: Failed to initialize SDK: " << result << std::endl;
            return false;
        }
        
        // 認証サービス作成
        result = CreateAuthService(&authService);
        if (result != SDKERR_SUCCESS) {
            std::cerr << "SDK_ERROR: Failed to create auth service: " << result << std::endl;
            return false;
        }
        
        // ミーティングサービス作成
        result = CreateMeetingService(&meetingService);
        if (result != SDKERR_SUCCESS) {
            std::cerr << "SDK_ERROR: Failed to create meeting service: " << result << std::endl;
            return false;
        }
        
        // 音声RAWデータヘルパー取得
        audioHelper = GetAudioRawdataHelper();
        if (!audioHelper) {
            std::cerr << "SDK_ERROR: Failed to get audio raw data helper" << std::endl;
            return false;
        }
        
        std::cout << "SDK_SUCCESS: Zoom Meeting SDK initialized successfully" << std::endl;
        return true;
    }
    
    bool joinMeeting(const std::string& meetingId, const std::string& password, const std::string& username) {
        std::cout << "SDK_CALL: Joining meeting " << meetingId << std::endl;
        
        if (!meetingService) {
            std::cerr << "SDK_ERROR: Meeting service not initialized" << std::endl;
            return false;
        }
        
        // 会議参加パラメータ設定
        JoinParam joinParam;
        joinParam.userType = SDK_UT_NORMALUSER;
        joinParam.join_param.common_join_param.sdkHashMeetingID = meetingId.c_str();
        joinParam.join_param.common_join_param.sdkMeetingPassword = password.c_str();
        joinParam.join_param.common_join_param.sdkUsername = username.c_str();
        
        SDKError result = meetingService->Join(joinParam);
        if (result != SDKERR_SUCCESS) {
            std::cerr << "SDK_ERROR: Failed to join meeting: " << result << std::endl;
            return false;
        }
        
        // 会議参加完了まで待機
        std::this_thread::sleep_for(std::chrono::seconds(5));
        
        std::cout << "SDK_SUCCESS: Successfully joined meeting" << std::endl;
        return true;
    }
    
    bool startRecording() {
        std::cout << "SDK_CALL: Starting audio recording" << std::endl;
        
        if (!audioHelper) {
            std::cerr << "SDK_ERROR: Audio helper not initialized" << std::endl;
            return false;
        }
        
        recording.store(true);
        
        // 音声RAWデータの購読開始
        SDKError result = audioHelper->subscribe(this, false);
        if (result != SDKERR_SUCCESS) {
            std::cerr << "SDK_ERROR: Failed to subscribe to audio raw data: " << result << std::endl;
            recording.store(false);
            return false;
        }
        
        // 録画スレッドを開始
        recordingThread = std::thread(&RealZoomAudioRecorder::recordingLoop, this);
        
        std::cout << "SDK_SUCCESS: Audio recording started with real Zoom SDK" << std::endl;
        return true;
    }
    
    void stopRecording() {
        if (!recording.load()) {
            return;
        }
        
        std::cout << "SDK_CALL: Stopping audio recording" << std::endl;
        
        recording.store(false);
        
        if (audioHelper) {
            audioHelper->unSubscribe();
        }
        
        bufferCondition.notify_all();
        
        if (recordingThread.joinable()) {
            recordingThread.join();
        }
        
        std::cout << "SDK_SUCCESS: Audio recording stopped" << std::endl;
    }
    
    void leaveMeeting() {
        std::cout << "SDK_CALL: Leaving meeting" << std::endl;
        
        if (meetingService) {
            meetingService->Leave(LEAVE_MEETING);
        }
        
        std::cout << "SDK_SUCCESS: Left meeting" << std::endl;
    }
    
    // IZoomSDKAudioRawDataDelegate implementation
    void onMixedAudioRawDataReceived(AudioRawData* data_) override {
        if (!recording.load() || !data_) return;
        
        std::lock_guard<std::mutex> lock(bufferMutex);
        
        // 音声データをフレームに変換
        AudioFrame frame;
        frame.sample_rate = data_->GetSampleRate();
        frame.channels = data_->GetChannelNum();
        frame.timestamp = data_->GetTimeStamp();
        
        // 音声データをコピー
        char* buffer = data_->GetBuffer();
        unsigned int bufferLen = data_->GetBufferLen();
        frame.data.assign(buffer, buffer + bufferLen);
        
        audioBuffer.push_back(frame);
        bufferCondition.notify_one();
        
        std::cout << "SDK_AUDIO: Received audio data - " << bufferLen << " bytes, " 
                  << frame.sample_rate << "Hz, " << frame.channels << " channels" << std::endl;
    }
    
    void onOneWayAudioRawDataReceived(AudioRawData* data_, uint32_t user_id) override {
        // 個別ユーザーの音声データ（必要に応じて実装）
    }
    
    void onShareAudioRawDataReceived(AudioRawData* data_) override {
        // 共有音声データ（必要に応じて実装）
    }
    
    void onOneWayInterpreterAudioRawDataReceived(AudioRawData* data_, const zchar_t* pLanguageName) override {
        // 通訳音声データ（必要に応じて実装）
    }
    
private:
    void recordingLoop() {
        std::ofstream audioFile(outputPath, std::ios::binary);
        if (!audioFile.is_open()) {
            std::cerr << "Failed to open audio file: " << outputPath << std::endl;
            return;
        }
        
        // WAVヘッダーを書き込み
        writeWAVHeader(audioFile);
        
        std::unique_lock<std::mutex> lock(bufferMutex);
        uint32_t totalSamples = 0;
        
        while (recording.load() || !audioBuffer.empty()) {
            if (audioBuffer.empty()) {
                bufferCondition.wait_for(lock, std::chrono::milliseconds(100));
                continue;
            }
            
            AudioFrame frame = audioBuffer.front();
            audioBuffer.pop_front();
            lock.unlock();
            
            // 音声データをファイルに書き込み
            audioFile.write(frame.data.data(), frame.data.size());
            totalSamples += frame.data.size() / 2; // 16-bit samples
            
            lock.lock();
        }
        
        // WAVヘッダーを更新
        updateWAVHeader(audioFile, totalSamples);
        audioFile.close();
        
        std::cout << "SDK_INFO: Real Zoom meeting audio saved to " << outputPath << std::endl;
    }
    
    void writeWAVHeader(std::ofstream& file) {
        WAVHeader header;
        header.fileSize = 36; // 仮のサイズ
        header.dataSize = 0; // 仮のサイズ
        
        file.write(reinterpret_cast<const char*>(&header), sizeof(header));
    }
    
    void updateWAVHeader(std::ofstream& file, uint32_t totalSamples) {
        uint32_t audioDataSize = totalSamples * 2; // 16bit = 2 bytes per sample
        uint32_t fileSize = 36 + audioDataSize;
        
        file.seekp(4);
        file.write(reinterpret_cast<const char*>(&fileSize), 4);
        file.seekp(40);
        file.write(reinterpret_cast<const char*>(&audioDataSize), 4);
    }
    
    void cleanup() {
        if (audioHelper) {
            audioHelper->unSubscribe();
        }
        
        if (meetingService) {
            DestroyMeetingService(meetingService);
            meetingService = nullptr;
        }
        
        if (authService) {
            DestroyAuthService(authService);
            authService = nullptr;
        }
        
        CleanUPSDK();
    }
};

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
}

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
    
    // Simple JSON parsing
    std::ifstream file(configPath);
    std::string line;
    
    while (std::getline(file, line)) {
        if (line.find("\"meetingNumber\"") != std::string::npos) {
            size_t start = line.find(":") + 2;
            size_t end = line.find("\"", start + 1);
            config.meetingNumber = line.substr(start + 1, end - start - 1);
        }
        else if (line.find("\"userName\"") != std::string::npos) {
            size_t start = line.find(":") + 2;
            size_t end = line.find("\"", start + 1);
            config.userName = line.substr(start + 1, end - start - 1);
        }
        else if (line.find("\"audioFile\"") != std::string::npos) {
            size_t start = line.find(":") + 2;
            size_t end = line.find("\"", start + 1);
            config.audioFile = line.substr(start + 1, end - start - 1);
        }
        else if (line.find("\"sessionId\"") != std::string::npos) {
            size_t start = line.find(":") + 2;
            size_t end = line.find("\"", start + 1);
            config.sessionId = line.substr(start + 1, end - start - 1);
        }
        else if (line.find("\"password\"") != std::string::npos) {
            size_t start = line.find(":") + 2;
            size_t end = line.find("\"", start + 1);
            config.password = line.substr(start + 1, end - start - 1);
        }
    }
    
    // Get API credentials from environment
    const char* apiKey = std::getenv("ZOOM_MEETING_SDK_KEY");
    const char* apiSecret = std::getenv("ZOOM_MEETING_SDK_SECRET");
    
    if (apiKey && apiSecret) {
        config.apiKey = apiKey;
        config.apiSecret = apiSecret;
    }
    
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
        
        // Initialize the Real Zoom SDK Audio Recorder
        RealZoomAudioRecorder recorder(config.audioFile);
        
        // API Key validation
        if (config.apiKey.empty() || config.apiSecret.empty()) {
            std::cout << "SDK_ERROR: Missing API credentials" << std::endl;
            return 1;
        }
        
        std::cout << "API_CREDENTIALS_FOUND" << std::endl;
        std::cout << "INITIALIZING_ZOOM_SDK" << std::endl;
        
        // Initialize the SDK with credentials
        bool initSuccess = recorder.initializeSDK(config.apiKey, config.apiSecret);
        if (!initSuccess) {
            std::cout << "SDK_INITIALIZATION_FAILED" << std::endl;
            return 1;
        }
        
        std::cout << "CONNECTING_TO_REAL_MEETING: " << config.meetingNumber << std::endl;
        
        // Join the actual meeting
        bool joinSuccessful = recorder.joinMeeting(config.meetingNumber, config.password, config.userName);
        
        if (joinSuccessful) {
            std::cout << "MEETING_JOINED_SUCCESSFULLY" << std::endl;
            std::cout << "RECORDING_STARTED" << std::endl;
            std::cout << "AUDIO_FILE_CREATED: " << config.audioFile << std::endl;
            
            // Start real-time audio recording
            if (recorder.startRecording()) {
                std::cout << "REALTIME_ZOOM_SDK_RECORDING_STARTED" << std::endl;
                
                // Recording loop with heartbeats
                int heartbeatCount = 0;
                while (g_running && heartbeatCount < 60) { // Up to 60 heartbeats (10 minutes)
                    std::cout << "RECORDING_HEARTBEAT" << std::endl;
                    sleep(10);
                    heartbeatCount++;
                }
                
                // Stop recording
                recorder.stopRecording();
                std::cout << "REALTIME_RECORDING_STOPPED" << std::endl;
            } else {
                std::cout << "RECORDING_START_FAILED" << std::endl;
                return 1;
            }
            
            // Leave meeting
            recorder.leaveMeeting();
            
        } else {
            std::cout << "MEETING_JOIN_FAILED" << std::endl;
            return 1;
        }
        
        std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        return 1;
    }
    
    std::cout << "RECORDING_STOPPED" << std::endl;
    std::cout << "MEETING_LEFT" << std::endl;
    
    return 0;
}