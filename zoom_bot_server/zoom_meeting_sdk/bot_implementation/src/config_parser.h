#pragma once

#include <string>

class ConfigParser {
public:
    explicit ConfigParser(const std::string& configPath);
    
    // Getters
    const std::string& getMeetingNumber() const { return meetingNumber_; }
    const std::string& getPassword() const { return password_; }
    const std::string& getUserName() const { return userName_; }
    const std::string& getAudioFile() const { return audioFile_; }
    const std::string& getVideoFile() const { return videoFile_; }
    const std::string& getSessionId() const { return sessionId_; }
    const std::string& getUploadedFileId() const { return uploadedFileId_; }
    const std::string& getOutputPath() const { return outputPath_; }
    
    // SDK Keys (from environment)
    const std::string& getSDKKey() const { return sdkKey_; }
    const std::string& getSDKSecret() const { return sdkSecret_; }
    
private:
    void loadFromFile(const std::string& configPath);
    void loadEnvironmentVariables();
    
    std::string meetingNumber_;
    std::string password_;
    std::string userName_;
    std::string audioFile_;
    std::string videoFile_;
    std::string sessionId_;
    std::string uploadedFileId_;
    std::string outputPath_;
    
    // Environment variables
    std::string sdkKey_;
    std::string sdkSecret_;
};