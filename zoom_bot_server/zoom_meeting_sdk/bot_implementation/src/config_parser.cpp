#include "config_parser.h"
#include <fstream>
#include <json/json.h>
#include <cstdlib>
#include <stdexcept>

ConfigParser::ConfigParser(const std::string& configPath) {
    loadFromFile(configPath);
    loadEnvironmentVariables();
}

void ConfigParser::loadFromFile(const std::string& configPath) {
    std::ifstream file(configPath);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open config file: " + configPath);
    }
    
    Json::Value root;
    Json::CharReaderBuilder builder;
    std::string errors;
    
    if (!Json::parseFromStream(builder, file, &root, &errors)) {
        throw std::runtime_error("JSON parse error: " + errors);
    }
    
    // Extract configuration values
    meetingNumber_ = root.get("meetingNumber", "").asString();
    password_ = root.get("password", "").asString();
    userName_ = root.get("userName", "Recording Bot").asString();
    audioFile_ = root.get("audioFile", "").asString();
    videoFile_ = root.get("videoFile", "").asString();
    sessionId_ = root.get("sessionId", "").asString();
    uploadedFileId_ = root.get("uploadedFileId", "").asString();
    outputPath_ = root.get("outputPath", "").asString();
    
    // Validate required fields
    if (meetingNumber_.empty()) {
        throw std::runtime_error("Meeting number is required");
    }
    if (audioFile_.empty()) {
        throw std::runtime_error("Audio file path is required");
    }
}

void ConfigParser::loadEnvironmentVariables() {
    const char* sdkKey = std::getenv("ZOOM_MEETING_SDK_KEY");
    const char* sdkSecret = std::getenv("ZOOM_MEETING_SDK_SECRET");
    
    if (!sdkKey || !sdkSecret) {
        throw std::runtime_error("ZOOM_MEETING_SDK_KEY and ZOOM_MEETING_SDK_SECRET environment variables are required");
    }
    
    sdkKey_ = sdkKey;
    sdkSecret_ = sdkSecret;
}