cmake_minimum_required(VERSION 3.16)
project(ZoomMeetingBot)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set Zoom SDK path
set(ZOOM_SDK_PATH ${CMAKE_SOURCE_DIR}/..)

# Include directories
include_directories(${ZOOM_SDK_PATH}/h)
include_directories(${CMAKE_SOURCE_DIR}/src)

# Hybrid bot executable (with dynamic SDK loading)
add_executable(zoom_meeting_bot src/hybrid_zoom_bot.cpp)

# Link libraries (minimal dependencies)
target_link_libraries(zoom_meeting_bot
    pthread
    dl
    m
)

# Set runtime library path for when SDK is available
set_target_properties(zoom_meeting_bot PROPERTIES
    INSTALL_RPATH "${ZOOM_SDK_PATH}:${ZOOM_SDK_PATH}/qt_libs/Qt/lib"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# Installation
install(TARGETS zoom_meeting_bot DESTINATION bin)