#pragma once

#include <string>
#include <fstream>
#include <memory>

struct WAVHeader {
    char riff[4] = {'R', 'I', 'F', 'F'};
    uint32_t fileSize = 0;
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

class AudioRecorder {
public:
    explicit AudioRecorder(const std::string& outputPath);
    ~AudioRecorder();
    
    bool initialize();
    bool startRecording();
    bool stopRecording();
    void writeAudioData(const char* data, size_t length);
    
    // Audio format settings
    static constexpr int SAMPLE_RATE = 16000;
    static constexpr int CHANNELS = 1;
    static constexpr int BITS_PER_SAMPLE = 16;
    
private:
    std::string outputPath_;
    std::unique_ptr<std::ofstream> audioFile_;
    WAVHeader header_;
    size_t totalDataSize_;
    bool isRecording_;
    
    void updateWAVHeader();
    void writeWAVHeader();
};