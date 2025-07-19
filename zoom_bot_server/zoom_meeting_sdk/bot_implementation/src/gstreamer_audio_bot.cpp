#include <iostream>
#include <string>
#include <signal.h>
#include <unistd.h>
#include <gst/gst.h>
#include <thread>

bool g_running = true;
GstElement* pipeline = nullptr;

void signalHandler(int signal) {
    std::cout << "STOPPING_RECORDING" << std::endl;
    g_running = false;
    
    if (pipeline) {
        gst_element_send_event(pipeline, gst_event_new_eos());
    }
}

class GStreamerAudioRecorder {
private:
    GstElement* pipeline;
    std::string outputPath;
    
public:
    GStreamerAudioRecorder(const std::string& output) : outputPath(output), pipeline(nullptr) {}
    
    bool initialize() {
        gst_init(nullptr, nullptr);
        
        // Create pipeline to capture from PulseAudio
        std::string pipelineStr = 
            "pulsesrc device=zoom_sink.monitor ! "
            "audio/x-raw,rate=16000,channels=1 ! "
            "audioconvert ! "
            "audioresample ! "
            "wavenc ! "
            "filesink location=" + outputPath;
        
        GError* error = nullptr;
        pipeline = gst_parse_launch(pipelineStr.c_str(), &error);
        
        if (error) {
            std::cerr << "Pipeline creation failed: " << error->message << std::endl;
            g_error_free(error);
            
            // Fallback pipeline for default audio
            std::cout << "Trying fallback pipeline..." << std::endl;
            pipelineStr = 
                "autoaudiosrc ! "
                "audio/x-raw,rate=16000,channels=1 ! "
                "audioconvert ! "
                "audioresample ! "
                "wavenc ! "
                "filesink location=" + outputPath;
            
            pipeline = gst_parse_launch(pipelineStr.c_str(), &error);
            if (error) {
                std::cerr << "Fallback pipeline also failed: " << error->message << std::endl;
                g_error_free(error);
                return false;
            }
        }
        
        std::cout << "GSTREAMER: Pipeline created successfully" << std::endl;
        return true;
    }
    
    bool start() {
        if (!pipeline) return false;
        
        // Start pipeline
        GstStateChangeReturn ret = gst_element_set_state(pipeline, GST_STATE_PLAYING);
        if (ret == GST_STATE_CHANGE_FAILURE) {
            std::cerr << "Failed to start pipeline" << std::endl;
            return false;
        }
        
        std::cout << "GSTREAMER: Recording started" << std::endl;
        return true;
    }
    
    void stop() {
        if (pipeline) {
            gst_element_send_event(pipeline, gst_event_new_eos());
            gst_element_set_state(pipeline, GST_STATE_NULL);
            gst_object_unref(pipeline);
            pipeline = nullptr;
        }
    }
    
    void waitForEOS() {
        if (!pipeline) return;
        
        GstBus* bus = gst_element_get_bus(pipeline);
        GstMessage* msg = gst_bus_timed_pop_filtered(bus, GST_CLOCK_TIME_NONE,
            (GstMessageType)(GST_MESSAGE_ERROR | GST_MESSAGE_EOS));
        
        if (msg != nullptr) {
            gst_message_unref(msg);
        }
        gst_object_unref(bus);
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
    
    std::cout << "STARTING_GSTREAMER_RECORDER" << std::endl;
    std::cout << "Output: " << outputPath << std::endl;
    
    GStreamerAudioRecorder recorder(outputPath);
    
    if (!recorder.initialize()) {
        std::cerr << "Failed to initialize GStreamer" << std::endl;
        return 1;
    }
    
    if (!recorder.start()) {
        std::cerr << "Failed to start recording" << std::endl;
        return 1;
    }
    
    std::cout << "RECORDING_STARTED" << std::endl;
    
    // Recording loop
    while (g_running) {
        std::cout << "RECORDING_HEARTBEAT" << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(10));
    }
    
    // Stop recording
    recorder.stop();
    
    std::cout << "RECORDING_STOPPED" << std::endl;
    
    return 0;
}