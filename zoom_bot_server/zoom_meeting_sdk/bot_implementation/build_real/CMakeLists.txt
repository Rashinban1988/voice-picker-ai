cmake_minimum_required(VERSION 3.16)
project(ZoomRealSDKBot)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compiler flags
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fPIC")
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

# SDK paths
set(ZOOM_SDK_PATH ${CMAKE_SOURCE_DIR}/..)
set(ZOOM_SDK_INCLUDE_DIR ${ZOOM_SDK_PATH}/h)
set(ZOOM_SDK_LIB_DIR ${ZOOM_SDK_PATH})

# Include directories
include_directories(${ZOOM_SDK_INCLUDE_DIR})
include_directories(${ZOOM_SDK_INCLUDE_DIR}/meeting_service_components)
include_directories(${ZOOM_SDK_INCLUDE_DIR}/rawdata)
include_directories(${CMAKE_SOURCE_DIR}/src)

# Find required libraries
find_package(Threads REQUIRED)

# Source files for real SDK integration
set(REAL_SDK_SOURCES
    src/zoom_sdk_integration.cpp
    src/real_sdk_main.cpp
)

# Create real SDK executable
add_executable(real_zoom_sdk_bot ${REAL_SDK_SOURCES})

# Link libraries
target_link_libraries(real_zoom_sdk_bot
    ${CMAKE_THREAD_LIBS_INIT}
    ${ZOOM_SDK_LIB_DIR}/libmeetingsdk.so
    dl
    m
)

# Set runtime library path
set_target_properties(real_zoom_sdk_bot PROPERTIES
    INSTALL_RPATH "${ZOOM_SDK_LIB_DIR}:${ZOOM_SDK_LIB_DIR}/qt_libs/Qt/lib"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# Also build the hybrid bot for fallback
add_executable(zoom_meeting_bot src/hybrid_zoom_bot.cpp)
target_link_libraries(zoom_meeting_bot
    pthread
    dl
    m
)
set_target_properties(zoom_meeting_bot PROPERTIES
    INSTALL_RPATH "${ZOOM_SDK_PATH}:${ZOOM_SDK_PATH}/qt_libs/Qt/lib"
    BUILD_WITH_INSTALL_RPATH TRUE
)

# Install targets
install(TARGETS real_zoom_sdk_bot zoom_meeting_bot DESTINATION bin)