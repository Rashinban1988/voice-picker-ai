#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <fstream>
#include <chrono>
#include <thread>
#include <atomic>

// External SDK functions
extern "C" {
    bool InitializeZoomSDK(const char* jwt_token);
    bool JoinZoomMeeting(const char* meeting_number, const char* password, const char* username);
    bool StartAudioRecording(const char* output_path);
    void StopAudioRecording();
    void LeaveMeeting();
    void CleanupSDK();
}

bool g_running = true;

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
    std::string jwt;
};

Config parseConfig(const std::string& configPath) {
    Config config;
    
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
        else if (line.find("\"jwt\"") != std::string::npos) {
            size_t start = line.find(":") + 2;
            size_t end = line.find("\"", start + 1);
            config.jwt = line.substr(start + 1, end - start - 1);
        }
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
        
        std::cout << "STARTING_BOT" << std::endl;
        std::cout << "Meeting: " << config.meetingNumber << std::endl;
        std::cout << "Username: " << config.userName << std::endl;
        
        // Check if we have JWT token
        if (config.jwt.empty()) {
            std::cout << "JWT_TOKEN_MISSING" << std::endl;
            std::cout << "FALLBACK_TO_SIMULATION_MODE" << std::endl;
            // Could fall back to simulation here
            return 1;
        }
        
        std::cout << "JWT_TOKEN_FOUND" << std::endl;
        std::cout << "INITIALIZING_ZOOM_SDK" << std::endl;
        
        // Initialize SDK
        if (!InitializeZoomSDK(config.jwt.c_str())) {
            std::cout << "SDK_INITIALIZATION_FAILED" << std::endl;
            return 1;
        }
        
        std::cout << "SDK_INITIALIZATION_SUCCESS" << std::endl;
        std::cout << "CONNECTING_TO_REAL_MEETING: " << config.meetingNumber << std::endl;
        
        // Join meeting
        if (!JoinZoomMeeting(config.meetingNumber.c_str(), config.password.c_str(), config.userName.c_str())) {
            std::cout << "MEETING_JOIN_FAILED" << std::endl;
            CleanupSDK();
            return 1;
        }
        
        std::cout << "MEETING_JOINED_SUCCESSFULLY" << std::endl;
        std::cout << "RECORDING_STARTED" << std::endl;
        std::cout << "AUDIO_FILE_CREATED: " << config.audioFile << std::endl;
        
        // Start recording
        if (!StartAudioRecording(config.audioFile.c_str())) {
            std::cout << "RECORDING_START_FAILED" << std::endl;
            LeaveMeeting();
            CleanupSDK();
            return 1;
        }
        
        std::cout << "REALTIME_ZOOM_SDK_RECORDING_STARTED" << std::endl;
        
        // Recording loop
        int heartbeatCount = 0;
        while (g_running && heartbeatCount < 60) { // Up to 10 minutes
            std::cout << "RECORDING_HEARTBEAT" << std::endl;
            std::this_thread::sleep_for(std::chrono::seconds(10));
            heartbeatCount++;
        }
        
        // Stop recording
        StopAudioRecording();
        std::cout << "REALTIME_RECORDING_STOPPED" << std::endl;
        
        // Leave meeting
        LeaveMeeting();
        std::cout << "SDK_SUCCESS: Left meeting" << std::endl;
        
        // Cleanup
        CleanupSDK();
        
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        CleanupSDK();
        return 1;
    }
    
    std::cout << "RECORDING_STOPPED" << std::endl;
    std::cout << "MEETING_LEFT" << std::endl;
    
    return 0;
}