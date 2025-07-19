#include <iostream>
#include <dlfcn.h>
#include <string>
#include <cstdlib>

// Simple SDK test - no headers, just dlopen/dlsym approach
int main() {
    std::cout << "=== Zoom SDK Direct Function Test ===" << std::endl;
    
    // Set library path
    const char* currentPath = std::getenv("LD_LIBRARY_PATH");
    std::string newPath = "/app/zoom_meeting_sdk:/app/zoom_meeting_sdk/qt_libs/Qt/lib";
    if (currentPath) {
        newPath += ":" + std::string(currentPath);
    }
    setenv("LD_LIBRARY_PATH", newPath.c_str(), 1);
    
    // Load SDK
    void* handle = dlopen("/app/zoom_meeting_sdk/libmeetingsdk.so", RTLD_LAZY | RTLD_GLOBAL);
    if (!handle) {
        std::cerr << "Failed to load SDK: " << dlerror() << std::endl;
        return 1;
    }
    
    std::cout << "✓ SDK library loaded successfully" << std::endl;
    
    // Get function pointers
    typedef int (*InitSDK_t)(void*);
    typedef int (*CreateAuthService_t)(void**);
    typedef int (*CreateMeetingService_t)(void**);
    typedef int (*CleanUPSDK_t)();
    typedef bool (*HasRawdataLicense_t)();
    typedef void* (*GetAudioRawdataHelper_t)();
    
    InitSDK_t initSDK = (InitSDK_t)dlsym(handle, "InitSDK");
    CreateAuthService_t createAuth = (CreateAuthService_t)dlsym(handle, "CreateAuthService");
    CreateMeetingService_t createMeeting = (CreateMeetingService_t)dlsym(handle, "CreateMeetingService");
    CleanUPSDK_t cleanupSDK = (CleanUPSDK_t)dlsym(handle, "CleanUPSDK");
    HasRawdataLicense_t hasRawdata = (HasRawdataLicense_t)dlsym(handle, "HasRawdataLicense");
    GetAudioRawdataHelper_t getAudioHelper = (GetAudioRawdataHelper_t)dlsym(handle, "GetAudioRawdataHelper");
    
    std::cout << "Function loading results:" << std::endl;
    std::cout << "  InitSDK: " << (initSDK ? "✓" : "✗") << std::endl;
    std::cout << "  CreateAuthService: " << (createAuth ? "✓" : "✗") << std::endl;
    std::cout << "  CreateMeetingService: " << (createMeeting ? "✓" : "✗") << std::endl;
    std::cout << "  CleanUPSDK: " << (cleanupSDK ? "✓" : "✗") << std::endl;
    std::cout << "  HasRawdataLicense: " << (hasRawdata ? "✓" : "✗") << std::endl;
    std::cout << "  GetAudioRawdataHelper: " << (getAudioHelper ? "✓" : "✗") << std::endl;
    
    // Test HasRawdataLicense
    if (hasRawdata) {
        bool hasLicense = hasRawdata();
        std::cout << "Raw data license: " << (hasLicense ? "Available" : "Not available") << std::endl;
    }
    
    // Test GetAudioRawdataHelper
    if (getAudioHelper) {
        void* audioHelper = getAudioHelper();
        std::cout << "Audio helper: " << (audioHelper ? "Available" : "Not available") << std::endl;
    }
    
    std::cout << "=== Test Complete ===" << std::endl;
    
    // Cleanup
    dlclose(handle);
    return 0;
}