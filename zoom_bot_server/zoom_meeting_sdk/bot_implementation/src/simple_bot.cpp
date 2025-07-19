#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <fstream>
#include <cmath>

bool g_running = true;

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
}

struct Config {
    std::string meetingNumber;
    std::string userName;
    std::string audioFile;
    std::string sessionId;
};

Config parseConfig(const std::string& configPath) {
    Config config;
    
    // Simple JSON parsing (for demo purposes)
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
    }
    
    return config;
}

void generateTestAudio(const std::string& audioPath, int durationSeconds = 30) {
    std::ofstream audioFile(audioPath, std::ios::binary);
    
    // WAV header
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
        uint32_t dataSize;
    };
    
    const int sampleRate = 16000;
    const int samples = sampleRate * durationSeconds;
    const int dataSize = samples * 2; // 16bit = 2 bytes per sample
    
    WAVHeader header;
    header.fileSize = sizeof(WAVHeader) - 8 + dataSize;
    header.dataSize = dataSize;
    
    // Write header
    audioFile.write(reinterpret_cast<const char*>(&header), sizeof(header));
    
    // Generate test audio (mixed frequencies for more realistic sound)
    for (int i = 0; i < samples; i++) {
        // Mix of frequencies to simulate voice
        double time = static_cast<double>(i) / sampleRate;
        double sample = 0.0;
        
        // Fundamental frequency (simulating voice)
        sample += 0.3 * std::sin(2 * M_PI * 200 * time);  // 200Hz
        sample += 0.2 * std::sin(2 * M_PI * 400 * time);  // 400Hz
        sample += 0.1 * std::sin(2 * M_PI * 800 * time);  // 800Hz
        
        // Add some noise for realism
        sample += 0.05 * (static_cast<double>(rand()) / RAND_MAX - 0.5);
        
        // Convert to 16-bit PCM
        int16_t pcmSample = static_cast<int16_t>(sample * 32767 * 0.8); // 80% volume
        audioFile.write(reinterpret_cast<const char*>(&pcmSample), sizeof(pcmSample));
    }
    
    audioFile.close();
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
        
        // Simulate authentication
        sleep(2);
        std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
        
        // Simulate joining meeting
        sleep(3);
        std::cout << "MEETING_JOINED" << std::endl;
        
        // Start recording
        sleep(1);
        std::cout << "RECORDING_STARTED" << std::endl;
        std::cout << "AUDIO_FILE_CREATED: " << config.audioFile << std::endl;
        
        // Generate realistic test audio
        generateTestAudio(config.audioFile, 30);
        
        // Heartbeat loop
        int heartbeatCount = 0;
        while (g_running && heartbeatCount < 3) { // Limited to 3 heartbeats for demo
            std::cout << "RECORDING_HEARTBEAT" << std::endl;
            sleep(10);
            heartbeatCount++;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        return 1;
    }
    
    std::cout << "RECORDING_STOPPED" << std::endl;
    std::cout << "MEETING_LEFT" << std::endl;
    
    return 0;
}