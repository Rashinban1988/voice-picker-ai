#pragma once

#include <string>
#include <memory>
#include "config_parser.h"
#include "audio_recorder.h"

// Forward declarations for Zoom SDK
namespace ZOOMSDK {
    class IZoomSDK;
    class IMeetingService;
    class IAuthService;
}

class ZoomBot {
public:
    explicit ZoomBot(const ConfigParser& config);
    ~ZoomBot();
    
    bool initialize();
    bool joinMeeting();
    bool startRecording();
    bool stopRecording();
    void processEvents();
    void cleanup();
    
private:
    ConfigParser config_;
    std::unique_ptr<AudioRecorder> audioRecorder_;
    
    // Zoom SDK interfaces
    ZOOMSDK::IZoomSDK* sdk_;
    ZOOMSDK::IMeetingService* meetingService_;
    ZOOMSDK::IAuthService* authService_;
    
    bool isInitialized_;
    bool isMeetingJoined_;
    bool isRecording_;
    
    // Helper methods
    bool authenticateSDK();
    std::string generateJWT() const;
    void onMeetingJoined();
    void onMeetingLeft();
    void onAudioDataReceived(const char* data, int length);
};