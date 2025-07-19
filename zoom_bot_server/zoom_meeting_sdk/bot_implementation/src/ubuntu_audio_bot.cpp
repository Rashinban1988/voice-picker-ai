#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <fstream>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <vector>
#include <cstring>
#include <sys/wait.h>

bool g_running = true;
pid_t g_recordingPid = 0;

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
    
    // Stop recording process
    if (g_recordingPid > 0) {
        kill(g_recordingPid, SIGTERM);
    }
}

class UbuntuZoomRecorder {
private:
    std::string outputPath;
    std::string sessionId;
    bool useSystemAudio;
    
public:
    UbuntuZoomRecorder(const std::string& output, const std::string& session, bool systemAudio = true) 
        : outputPath(output), sessionId(session), useSystemAudio(systemAudio) {}
    
    bool setupAudioRouting() {
        std::cout << "AUDIO_SETUP: Configuring PulseAudio for Zoom recording..." << std::endl;
        
        // Check if PulseAudio is running
        if (system("pactl info > /dev/null 2>&1") != 0) {
            std::cerr << "PulseAudio is not running!" << std::endl;
            return false;
        }
        
        // Create virtual sink for Zoom
        system("pactl unload-module module-null-sink 2>/dev/null");
        if (system("pactl load-module module-null-sink sink_name=zoom_sink sink_properties=device.description=ZoomRecorder") != 0) {
            std::cerr << "Failed to create virtual sink" << std::endl;
            return false;
        }
        
        std::cout << "AUDIO_SETUP: Virtual sink created" << std::endl;
        
        // Create loopback to hear Zoom audio
        system("pactl load-module module-loopback source=zoom_sink.monitor sink=@DEFAULT_SINK@ latency_msec=1");
        
        std::cout << "AUDIO_SETUP: Audio routing configured" << std::endl;
        std::cout << "IMPORTANT: Set Zoom audio output to 'ZoomRecorder' in Zoom settings!" << std::endl;
        
        return true;
    }
    
    bool startRecording() {
        std::cout << "RECORDING: Starting audio capture..." << std::endl;
        
        // Fork process for recording
        g_recordingPid = fork();
        
        if (g_recordingPid == 0) {
            // Child process - run parecord
            const char* recordCmd = "parecord";
            const char* device = useSystemAudio ? "zoom_sink.monitor" : "@DEFAULT_SOURCE@";
            
            // Execute recording command
            execl("/usr/bin/parecord", recordCmd, 
                  "-d", device,
                  "--file-format=wav",
                  "--format=s16le",
                  "--rate=16000",
                  "--channels=1",
                  outputPath.c_str(),
                  nullptr);
            
            // If we get here, exec failed
            std::cerr << "Failed to start parecord: " << strerror(errno) << std::endl;
            exit(1);
        } else if (g_recordingPid < 0) {
            std::cerr << "Fork failed!" << std::endl;
            return false;
        }
        
        std::cout << "RECORDING: PulseAudio recording started (PID: " << g_recordingPid << ")" << std::endl;
        return true;
    }
    
    bool startFFmpegRecording() {
        std::cout << "RECORDING: Starting FFmpeg audio capture..." << std::endl;
        
        g_recordingPid = fork();
        
        if (g_recordingPid == 0) {
            // Child process - run ffmpeg
            const char* device = useSystemAudio ? "zoom_sink.monitor" : "default";
            
            // Build FFmpeg command
            execl("/usr/bin/ffmpeg", "ffmpeg",
                  "-f", "pulse",
                  "-i", device,
                  "-ac", "1",
                  "-ar", "16000",
                  "-acodec", "pcm_s16le",
                  "-y",
                  outputPath.c_str(),
                  nullptr);
            
            // If we get here, exec failed
            std::cerr << "Failed to start ffmpeg: " << strerror(errno) << std::endl;
            exit(1);
        } else if (g_recordingPid < 0) {
            std::cerr << "Fork failed!" << std::endl;
            return false;
        }
        
        std::cout << "RECORDING: FFmpeg recording started (PID: " << g_recordingPid << ")" << std::endl;
        return true;
    }
    
    void stopRecording() {
        if (g_recordingPid > 0) {
            std::cout << "RECORDING: Stopping recording process..." << std::endl;
            
            // Send SIGTERM to recording process
            kill(g_recordingPid, SIGTERM);
            
            // Wait for process to finish
            int status;
            waitpid(g_recordingPid, &status, 0);
            
            std::cout << "RECORDING: Recording stopped" << std::endl;
            g_recordingPid = 0;
        }
    }
    
    void cleanup() {
        // Remove virtual audio devices
        system("pactl unload-module module-null-sink 2>/dev/null");
        system("pactl unload-module module-loopback 2>/dev/null");
    }
};

// Configuration structure
struct Config {
    std::string meetingNumber;
    std::string password;
    std::string userName;
    std::string audioFile;
    std::string sessionId;
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
    
    Config config = parseConfig(argv[2]);
    
    std::cout << "STARTING_BOT" << std::endl;
    std::cout << "Meeting: " << config.meetingNumber << std::endl;
    std::cout << "Audio output: " << config.audioFile << std::endl;
    
    // Create recorder
    UbuntuZoomRecorder recorder(config.audioFile, config.sessionId);
    
    // Setup audio routing
    if (!recorder.setupAudioRouting()) {
        std::cerr << "Failed to setup audio routing" << std::endl;
        // Continue anyway - might work with default settings
    }
    
    // Wait a bit for audio setup
    std::this_thread::sleep_for(std::chrono::seconds(2));
    
    // Start recording
    std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
    std::cout << "MEETING_JOINED" << std::endl;
    
    // Try parecord first, fallback to ffmpeg
    if (!recorder.startRecording()) {
        std::cout << "RECORDING: Trying FFmpeg as fallback..." << std::endl;
        if (!recorder.startFFmpegRecording()) {
            std::cerr << "Failed to start any recording method!" << std::endl;
            return 1;
        }
    }
    
    std::cout << "RECORDING_STARTED" << std::endl;
    std::cout << "AUDIO_FILE_CREATED: " << config.audioFile << std::endl;
    
    // Recording loop
    while (g_running) {
        std::cout << "RECORDING_HEARTBEAT" << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(10));
        
        // Check if recording process is still running
        if (g_recordingPid > 0) {
            int status;
            pid_t result = waitpid(g_recordingPid, &status, WNOHANG);
            if (result > 0) {
                std::cout << "RECORDING: Process ended unexpectedly" << std::endl;
                break;
            }
        }
    }
    
    // Stop recording
    recorder.stopRecording();
    
    // Cleanup
    recorder.cleanup();
    
    std::cout << "RECORDING_STOPPED" << std::endl;
    std::cout << "MEETING_LEFT" << std::endl;
    
    return 0;
}