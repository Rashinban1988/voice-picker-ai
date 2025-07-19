#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include "zoom_bot.h"
#include "config_parser.h"

bool g_running = true;

void signalHandler(int signal) {
    std::cout << "Received signal " << signal << ", shutting down..." << std::endl;
    g_running = false;
}

void printUsage(const char* programName) {
    std::cout << "Usage: " << programName << " --config <config.json>" << std::endl;
}

int main(int argc, char* argv[]) {
    // Parse command line arguments
    std::string configPath;
    
    for (int i = 1; i < argc; i++) {
        if (std::string(argv[i]) == "--config" && i + 1 < argc) {
            configPath = argv[i + 1];
            i++; // Skip next argument
        }
    }
    
    if (configPath.empty()) {
        printUsage(argv[0]);
        return 1;
    }
    
    // Set up signal handlers
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);
    
    try {
        // Parse configuration
        ConfigParser config(configPath);
        
        // Create and initialize bot
        ZoomBot bot(config);
        
        std::cout << "STARTING_BOT" << std::endl;
        std::cout << "Meeting: " << config.getMeetingNumber() << std::endl;
        std::cout << "Username: " << config.getUserName() << std::endl;
        
        // Initialize and start bot
        if (!bot.initialize()) {
            std::cerr << "ERROR: Failed to initialize bot" << std::endl;
            return 1;
        }
        
        if (!bot.joinMeeting()) {
            std::cerr << "ERROR: Failed to join meeting" << std::endl;
            return 1;
        }
        
        std::cout << "MEETING_JOINED" << std::endl;
        
        if (!bot.startRecording()) {
            std::cerr << "ERROR: Failed to start recording" << std::endl;
            return 1;
        }
        
        std::cout << "RECORDING_STARTED" << std::endl;
        std::cout << "AUDIO_FILE_CREATED: " << config.getAudioFile() << std::endl;
        
        // Main loop - send heartbeats
        while (g_running) {
            std::cout << "RECORDING_HEARTBEAT" << std::endl;
            
            // Process SDK events
            bot.processEvents();
            
            // Sleep for 10 seconds
            sleep(10);
        }
        
        // Cleanup
        std::cout << "STOPPING_RECORDING" << std::endl;
        bot.stopRecording();
        
        std::cout << "RECORDING_STOPPED" << std::endl;
        std::cout << "MEETING_LEFT" << std::endl;
        
        bot.cleanup();
        
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}