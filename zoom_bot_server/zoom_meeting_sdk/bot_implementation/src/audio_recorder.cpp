#include "audio_recorder.h"
#include <iostream>
#include <filesystem>

AudioRecorder::AudioRecorder(const std::string& outputPath)
    : outputPath_(outputPath), totalDataSize_(0), isRecording_(false) {
}

AudioRecorder::~AudioRecorder() {
    if (isRecording_) {
        stopRecording();
    }
}

bool AudioRecorder::initialize() {
    // Create output directory if it doesn't exist
    std::filesystem::path filePath(outputPath_);
    std::filesystem::path dirPath = filePath.parent_path();
    
    if (!std::filesystem::exists(dirPath)) {
        if (!std::filesystem::create_directories(dirPath)) {
            std::cerr << "Failed to create output directory: " << dirPath << std::endl;
            return false;
        }
    }
    
    return true;
}

bool AudioRecorder::startRecording() {
    if (isRecording_) {
        return true;
    }
    
    audioFile_ = std::make_unique<std::ofstream>(outputPath_, std::ios::binary);
    if (!audioFile_->is_open()) {
        std::cerr << "Failed to open audio file: " << outputPath_ << std::endl;
        return false;
    }
    
    // Write initial WAV header (will be updated later)
    writeWAVHeader();
    
    totalDataSize_ = 0;
    isRecording_ = true;
    
    return true;
}

bool AudioRecorder::stopRecording() {
    if (!isRecording_) {
        return true;
    }
    
    isRecording_ = false;
    
    if (audioFile_) {
        // Update WAV header with final sizes
        updateWAVHeader();
        audioFile_->close();
        audioFile_.reset();
    }
    
    std::cout << "Audio recording saved: " << outputPath_ 
              << " (size: " << totalDataSize_ << " bytes)" << std::endl;
    
    return true;
}

void AudioRecorder::writeAudioData(const char* data, size_t length) {
    if (!isRecording_ || !audioFile_) {
        return;
    }
    
    audioFile_->write(data, length);
    totalDataSize_ += length;
}

void AudioRecorder::writeWAVHeader() {
    if (!audioFile_) {
        return;
    }
    
    // Reset header values
    header_.fileSize = sizeof(WAVHeader) - 8 + totalDataSize_;
    header_.dataSize = totalDataSize_;
    
    audioFile_->seekp(0);
    audioFile_->write(reinterpret_cast<const char*>(&header_), sizeof(header_));
    audioFile_->seekp(0, std::ios::end);
}

void AudioRecorder::updateWAVHeader() {
    if (!audioFile_) {
        return;
    }
    
    // Update file size
    header_.fileSize = sizeof(WAVHeader) - 8 + totalDataSize_;
    header_.dataSize = totalDataSize_;
    
    // Seek to beginning and update header
    audioFile_->seekp(4);
    audioFile_->write(reinterpret_cast<const char*>(&header_.fileSize), sizeof(header_.fileSize));
    
    audioFile_->seekp(40);
    audioFile_->write(reinterpret_cast<const char*>(&header_.dataSize), sizeof(header_.dataSize));
    
    audioFile_->flush();
}