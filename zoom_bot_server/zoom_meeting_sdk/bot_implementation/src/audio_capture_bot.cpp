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

// Linux audio capture using ALSA or PulseAudio
#ifdef __linux__
#include <alsa/asoundlib.h>
#endif

bool g_running = true;

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
}

// WAV header structure
struct WAVHeader {
    char riff[4] = {'R', 'I', 'F', 'F'};
    uint32_t fileSize = 36;
    char wave[4] = {'W', 'A', 'V', 'E'};
    char fmt[4] = {'f', 'm', 't', ' '};
    uint32_t fmtSize = 16;
    uint16_t audioFormat = 1; // PCM
    uint16_t numChannels = 1; // Mono
    uint32_t sampleRate = 16000;
    uint32_t byteRate = 32000;
    uint16_t blockAlign = 2;
    uint16_t bitsPerSample = 16;
    char data[4] = {'d', 'a', 't', 'a'};
    uint32_t dataSize = 0;
};

class SystemAudioCapture {
private:
    std::string outputPath;
    std::ofstream audioFile;
    uint32_t totalSamples = 0;
    
#ifdef __linux__
    snd_pcm_t* capture_handle = nullptr;
#endif
    
public:
    SystemAudioCapture(const std::string& output) : outputPath(output) {}
    
    ~SystemAudioCapture() {
        stop();
    }
    
    bool start() {
        std::cout << "AUDIO_CAPTURE: Starting system audio capture" << std::endl;
        
        // Open output file
        audioFile.open(outputPath, std::ios::binary);
        if (!audioFile.is_open()) {
            std::cerr << "Failed to open output file: " << outputPath << std::endl;
            return false;
        }
        
        // Write WAV header
        WAVHeader header;
        audioFile.write(reinterpret_cast<const char*>(&header), sizeof(header));
        
#ifdef __linux__
        // Try to capture from ALSA loopback device
        int err;
        snd_pcm_hw_params_t* hw_params;
        
        // Try different capture devices
        const char* devices[] = {
            "default",           // Default capture device
            "pulse",            // PulseAudio
            "hw:Loopback,1",    // ALSA loopback device
            "plughw:0,0",       // First hardware device
            nullptr
        };
        
        for (int i = 0; devices[i] != nullptr; i++) {
            err = snd_pcm_open(&capture_handle, devices[i], SND_PCM_STREAM_CAPTURE, 0);
            if (err >= 0) {
                std::cout << "AUDIO_CAPTURE: Opened device: " << devices[i] << std::endl;
                break;
            }
        }
        
        if (err < 0) {
            std::cerr << "Cannot open audio device: " << snd_strerror(err) << std::endl;
            std::cout << "AUDIO_CAPTURE: Falling back to test audio generation" << std::endl;
            return true; // Continue with fallback
        }
        
        // Configure audio parameters
        snd_pcm_hw_params_alloca(&hw_params);
        snd_pcm_hw_params_any(capture_handle, hw_params);
        snd_pcm_hw_params_set_access(capture_handle, hw_params, SND_PCM_ACCESS_RW_INTERLEAVED);
        snd_pcm_hw_params_set_format(capture_handle, hw_params, SND_PCM_FORMAT_S16_LE);
        snd_pcm_hw_params_set_channels(capture_handle, hw_params, 1);
        
        unsigned int rate = 16000;
        snd_pcm_hw_params_set_rate_near(capture_handle, hw_params, &rate, 0);
        
        err = snd_pcm_hw_params(capture_handle, hw_params);
        if (err < 0) {
            std::cerr << "Cannot set audio parameters: " << snd_strerror(err) << std::endl;
            snd_pcm_close(capture_handle);
            capture_handle = nullptr;
            return true; // Continue with fallback
        }
        
        err = snd_pcm_prepare(capture_handle);
        if (err < 0) {
            std::cerr << "Cannot prepare audio interface: " << snd_strerror(err) << std::endl;
            snd_pcm_close(capture_handle);
            capture_handle = nullptr;
            return true; // Continue with fallback
        }
        
        std::cout << "AUDIO_CAPTURE: ALSA device configured successfully" << std::endl;
#endif
        
        return true;
    }
    
    void captureLoop() {
        const int bufferSize = 1600; // 100ms at 16kHz
        std::vector<int16_t> buffer(bufferSize);
        
        while (g_running) {
#ifdef __linux__
            if (capture_handle) {
                // Capture from ALSA
                int frames = snd_pcm_readi(capture_handle, buffer.data(), bufferSize);
                if (frames < 0) {
                    frames = snd_pcm_recover(capture_handle, frames, 0);
                }
                
                if (frames > 0) {
                    audioFile.write(reinterpret_cast<const char*>(buffer.data()), 
                                  frames * sizeof(int16_t));
                    totalSamples += frames;
                }
            } else
#endif
            {
                // Fallback: Generate test audio
                generateTestAudio(buffer.data(), bufferSize);
                audioFile.write(reinterpret_cast<const char*>(buffer.data()), 
                              bufferSize * sizeof(int16_t));
                totalSamples += bufferSize;
                
                // Sleep to simulate real-time capture
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
        }
    }
    
    void generateTestAudio(int16_t* buffer, int size) {
        static double phase = 0.0;
        const double frequency = 440.0; // A4 note
        const double sampleRate = 16000.0;
        
        for (int i = 0; i < size; i++) {
            double sample = 0.3 * sin(2 * M_PI * frequency * phase / sampleRate);
            buffer[i] = static_cast<int16_t>(sample * 32767);
            phase += 1.0;
            if (phase >= sampleRate) phase -= sampleRate;
        }
    }
    
    void stop() {
        if (audioFile.is_open()) {
            // Update WAV header
            audioFile.seekp(4);
            uint32_t fileSize = 36 + totalSamples * 2;
            audioFile.write(reinterpret_cast<const char*>(&fileSize), 4);
            
            audioFile.seekp(40);
            uint32_t dataSize = totalSamples * 2;
            audioFile.write(reinterpret_cast<const char*>(&dataSize), 4);
            
            audioFile.close();
            
            std::cout << "AUDIO_CAPTURE: Saved " << totalSamples << " samples" << std::endl;
        }
        
#ifdef __linux__
        if (capture_handle) {
            snd_pcm_close(capture_handle);
            capture_handle = nullptr;
        }
#endif
    }
};

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <output.wav>" << std::endl;
        return 1;
    }
    
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);
    
    std::string outputPath = argv[1];
    
    std::cout << "STARTING_AUDIO_CAPTURE" << std::endl;
    std::cout << "Output: " << outputPath << std::endl;
    
    // Note: To capture Zoom audio on Linux:
    // 1. Install ALSA loopback module: sudo modprobe snd-aloop
    // 2. Configure PulseAudio to route Zoom audio to loopback
    // 3. Or use PulseAudio monitor source
    
    SystemAudioCapture capture(outputPath);
    if (!capture.start()) {
        return 1;
    }
    
    std::cout << "CAPTURING_AUDIO" << std::endl;
    std::cout << "Press Ctrl+C to stop..." << std::endl;
    
    // Capture audio
    capture.captureLoop();
    
    // Stop and save
    capture.stop();
    
    std::cout << "AUDIO_CAPTURE_COMPLETE" << std::endl;
    return 0;
}