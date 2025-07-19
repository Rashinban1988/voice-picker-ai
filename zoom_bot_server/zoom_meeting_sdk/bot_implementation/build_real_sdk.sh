#!/bin/bash

# Build the real SDK bot
cd /app/zoom_meeting_sdk/bot_implementation

echo "Building real SDK bot..."
g++ -std=c++17 -fPIC -I../h -I../h/meeting_service_components -I../h/rawdata \
    -o build/real_zoom_sdk_bot \
    src/real_zoom_sdk_bot.cpp \
    -L.. -lmeetingsdk \
    -lpthread -ldl -lm

if [ $? -eq 0 ]; then
    echo "Build successful!"
    echo "Binary created: build/real_zoom_sdk_bot"
else
    echo "Build failed!"
fi