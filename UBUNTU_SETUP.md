# Ubuntu Linux での Zoom Meeting SDK セットアップガイド

## 1. システム要件

- Ubuntu 18.04/20.04/22.04 LTS
- 最小4GB RAM (8GB推奨)
- 2GB以上の空きディスク容量
- インターネット接続

## 2. 依存関係のインストール

### 基本ツールのインストール
```bash
# システムアップデート
sudo apt update && sudo apt upgrade -y

# 開発ツールのインストール
sudo apt install -y \
    build-essential \
    cmake \
    pkg-config \
    curl \
    wget \
    git \
    unzip \
    software-properties-common
```

### 音声・映像関連ライブラリのインストール
```bash
# 音声システム
sudo apt install -y \
    libasound2-dev \
    libpulse-dev \
    pulseaudio \
    pulseaudio-utils

# 映像関連
sudo apt install -y \
    libssl-dev \
    libcurl4-openssl-dev \
    libx11-dev \
    libxext-dev \
    libxrandr-dev \
    libxi-dev \
    libxss-dev \
    libglib2.0-dev \
    libgtk-3-dev
```

### Node.js 18のインストール
```bash
# NodeSource リポジトリ追加
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -

# Node.js インストール
sudo apt install -y nodejs

# バージョン確認
node --version
npm --version
```

### Python 3.9+ のインストール
```bash
# Python 3.9 インストール
sudo apt install -y python3.9 python3.9-dev python3.9-venv python3-pip

# シンボリックリンク作成
sudo ln -sf /usr/bin/python3.9 /usr/bin/python3
sudo ln -sf /usr/bin/python3.9 /usr/bin/python
```

## 3. Zoom Meeting SDK のセットアップ

### SDK ダウンロード
```bash
# 作業ディレクトリ作成
mkdir -p ~/zoom-sdk
cd ~/zoom-sdk

# Zoom Meeting SDK for Linux をダウンロード
# 注意: 実際のダウンロードは Zoom Developer Portal から行う必要があります
# https://developers.zoom.us/docs/meeting-sdk/linux/

# ダウンロード例 (実際のURLは異なる場合があります)
wget https://zoom.us/client/5.17.11.3835/zoom-meeting-sdk-linux_x86_64-5.17.11.3835.tar.gz

# 解凍
tar -xzf zoom-meeting-sdk-linux_x86_64-*.tar.gz
cd zoom-meeting-sdk-linux_x86_64
```

### SDK 設定
```bash
# 共有ライブラリのシンボリックリンク作成
ln -s libmeetingsdk.so libmeetingsdk.so.1

# システムライブラリパスに追加
sudo cp libmeetingsdk.so* /usr/local/lib/
sudo ldconfig

# 設定ディレクトリ作成
mkdir -p ~/.config.us

# 設定ファイル作成
cat > ~/.config.us/zoomus.conf << EOF
[General]
enable_headless=true
enable_xdisplay=false
enable_pipewire=true
audio_device=default
video_device=none
EOF
```

## 4. PulseAudio の設定（ヘッドレス環境用）

### PulseAudio システムサービス設定
```bash
# PulseAudio システムサービス有効化
sudo nano /etc/pulse/system.pa

# 以下の行をファイルの最後に追加:
load-module module-null-sink sink_name=zoom_sink
load-module module-null-source source_name=zoom_source
set-default-sink zoom_sink
set-default-source zoom_source
```

### PulseAudio 起動スクリプト
```bash
# スクリプト作成
cat > ~/setup-audio.sh << 'EOF'
#!/bin/bash

# PulseAudio サービス停止
sudo systemctl stop pulseaudio

# PulseAudio をシステムモードで起動
sudo pulseaudio --system --daemonize --verbose

# 少し待機
sleep 2

# ダミーデバイス作成
sudo -u pulse pactl load-module module-null-sink sink_name=zoom_sink
sudo -u pulse pactl load-module module-null-source source_name=zoom_source

# デフォルトに設定
sudo -u pulse pactl set-default-sink zoom_sink
sudo -u pulse pactl set-default-source zoom_source

echo "Audio setup completed"
EOF

# 実行権限付与
chmod +x ~/setup-audio.sh
```

## 5. プロジェクトのセットアップ

### アプリケーションのクローン・設定
```bash
# プロジェクトディレクトリに移動
cd /path/to/your/project

# Node.js依存関係インストール
cd zoom_bot_server
npm install

# Python仮想環境設定
cd ../macching_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # 必要な依存関係をインストール
```

### 環境変数設定
```bash
# Zoom Bot Server用環境変数
cd zoom_bot_server
cp .env.example .env

# 以下を編集
nano .env
```

```env
# Zoom Meeting SDK認証情報
ZOOM_MEETING_SDK_KEY=your_sdk_key_here
ZOOM_MEETING_SDK_SECRET=your_sdk_secret_here

# サーバー設定
PORT=4000
NODE_ENV=production

# Django連携用
DJANGO_API_URL=http://localhost:8000
DJANGO_API_TOKEN=your_django_token_here

# 録画保存設定
RECORDINGS_BASE_PATH=/var/recordings
```

### 録画ディレクトリ作成
```bash
# 録画用ディレクトリ作成
sudo mkdir -p /var/recordings
sudo chown $USER:$USER /var/recordings
sudo chmod 755 /var/recordings
```

## 6. Linux SDK Bot の実装

### C++ ボット実装（基本版）
```bash
# プロジェクトディレクトリに移動
cd zoom_bot_server/src/linux-sdk

# CMake プロジェクトファイル作成
cat > CMakeLists.txt << 'EOF'
cmake_minimum_required(VERSION 3.16)
project(ZoomBot)

set(CMAKE_CXX_STANDARD 17)

# Zoom SDK パスを設定
set(ZOOM_SDK_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../../zoom-meeting-sdk-linux_x86_64")

# インクルードディレクトリ
include_directories(${ZOOM_SDK_PATH}/include)

# ライブラリディレクトリ
link_directories(${ZOOM_SDK_PATH})

# 実行ファイル作成
add_executable(zoom-bot 
    main.cpp
    ZoomBot.cpp
)

# ライブラリリンク
target_link_libraries(zoom-bot 
    meetingsdk
    pthread
    curl
    ssl
    crypto
    asound
    pulse
    pulse-simple
)

# コンパイルオプション
target_compile_options(zoom-bot PRIVATE -Wall -Wextra)
EOF
```

### メインプログラム作成
```bash
cat > main.cpp << 'EOF'
#include <iostream>
#include <string>
#include <unistd.h>
#include <signal.h>
#include <fstream>
#include <json/json.h>
#include "ZoomBot.h"

volatile bool keep_running = true;

void signal_handler(int signum) {
    std::cout << "Received signal " << signum << std::endl;
    keep_running = false;
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " --config <config.json>" << std::endl;
        return 1;
    }

    std::string config_path;
    for (int i = 1; i < argc; i++) {
        if (std::string(argv[i]) == "--config" && i + 1 < argc) {
            config_path = argv[i + 1];
            break;
        }
    }

    if (config_path.empty()) {
        std::cerr << "Config file not specified" << std::endl;
        return 1;
    }

    // 設定ファイル読み込み
    std::ifstream config_file(config_path);
    if (!config_file.is_open()) {
        std::cerr << "Cannot open config file: " << config_path << std::endl;
        return 1;
    }

    Json::Value config;
    config_file >> config;
    config_file.close();

    // シグナルハンドラー設定
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    // ボット初期化
    ZoomBot bot;
    
    try {
        // 設定適用
        bot.configure(config);
        
        // ボット開始
        bot.start();
        
        // 実行継続
        while (keep_running) {
            usleep(100000); // 100ms待機
        }
        
        // 停止処理
        bot.stop();
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
EOF
```

### ZoomBot クラス実装
```bash
cat > ZoomBot.h << 'EOF'
#ifndef ZOOM_BOT_H
#define ZOOM_BOT_H

#include <string>
#include <memory>
#include <json/json.h>
#include "meeting_service_interface.h"
#include "auth_service_interface.h"

using namespace ZOOM_SDK_NAMESPACE;

class ZoomBot : public IAuthServiceEvent, public IMeetingServiceEvent {
public:
    ZoomBot();
    ~ZoomBot();
    
    void configure(const Json::Value& config);
    void start();
    void stop();
    
    // IAuthServiceEvent
    void onAuthenticationReturn(AuthResult result) override;
    void onLoginRet(PluginLoginResult result) override;
    void onLogoutRet(PluginLogoutResult result) override;
    
    // IMeetingServiceEvent
    void onMeetingStatusChanged(MeetingStatus status, int result) override;
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override;
    void onMeetingParameterNotification(const MeetingParameter* meeting_param) override;
    
private:
    Json::Value config_;
    IAuthService* auth_service_;
    IMeetingService* meeting_service_;
    std::string output_path_;
    bool is_running_;
    bool is_recording_;
    
    void initializeSDK();
    void cleanupSDK();
    void joinMeeting();
    void startRecording();
    void stopRecording();
    void saveAudioData(const char* data, size_t size);
};

#endif // ZOOM_BOT_H
EOF
```

```bash
cat > ZoomBot.cpp << 'EOF'
#include "ZoomBot.h"
#include <iostream>
#include <fstream>
#include <filesystem>
#include <cstring>

ZoomBot::ZoomBot() 
    : auth_service_(nullptr)
    , meeting_service_(nullptr)
    , is_running_(false)
    , is_recording_(false) {
}

ZoomBot::~ZoomBot() {
    cleanupSDK();
}

void ZoomBot::configure(const Json::Value& config) {
    config_ = config;
    output_path_ = config["outputPath"].asString();
    
    // 出力ディレクトリ作成
    std::filesystem::create_directories(output_path_);
}

void ZoomBot::start() {
    std::cout << "STARTING_BOT" << std::endl;
    
    try {
        initializeSDK();
        is_running_ = true;
        
        // 認証開始
        AuthContext auth_context;
        auth_context.jwt_token = config_["jwt"].asString().c_str();
        
        auth_service_->SDKAuth(auth_context);
        
    } catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << std::endl;
        throw;
    }
}

void ZoomBot::stop() {
    std::cout << "STOPPING_RECORDING" << std::endl;
    
    is_running_ = false;
    
    if (is_recording_) {
        stopRecording();
    }
    
    if (meeting_service_) {
        meeting_service_->Leave(LEAVE_MEETING);
    }
    
    cleanupSDK();
    
    std::cout << "MEETING_LEFT" << std::endl;
}

void ZoomBot::initializeSDK() {
    InitParam init_param;
    init_param.strWebDomain = L"https://zoom.us";
    init_param.strSupportUrl = L"https://zoom.us";
    init_param.strDirPath = L"./";
    init_param.enableLogByDefault = false;
    init_param.enableSdkLogByDefault = false;
    
    SDKError error = InitSDK(init_param);
    if (error != SDKERR_SUCCESS) {
        throw std::runtime_error("Failed to initialize SDK: " + std::to_string(error));
    }
    
    auth_service_ = CreateAuthService();
    if (!auth_service_) {
        throw std::runtime_error("Failed to create auth service");
    }
    
    auth_service_->SetEvent(this);
    
    meeting_service_ = CreateMeetingService();
    if (!meeting_service_) {
        throw std::runtime_error("Failed to create meeting service");
    }
    
    meeting_service_->SetEvent(this);
}

void ZoomBot::cleanupSDK() {
    if (auth_service_) {
        auth_service_->SetEvent(nullptr);
        auth_service_ = nullptr;
    }
    
    if (meeting_service_) {
        meeting_service_->SetEvent(nullptr);
        meeting_service_ = nullptr;
    }
    
    CleanupSDK();
}

void ZoomBot::joinMeeting() {
    JoinParam join_param;
    join_param.userType = SDK_UT_WITHOUT_LOGIN;
    
    JoinParam4WithoutLogin& login_param = join_param.param.withoutloginParam;
    login_param.meetingNumber = std::stoull(config_["meetingNumber"].asString());
    login_param.userName = config_["userName"].asString().c_str();
    login_param.psw = config_["password"].asString().c_str();
    login_param.vanityID = nullptr;
    login_param.customer_key = nullptr;
    login_param.webinar_token = nullptr;
    login_param.isAudioOff = false;
    login_param.isVideoOff = true;
    
    SDKError error = meeting_service_->Join(join_param);
    if (error != SDKERR_SUCCESS) {
        throw std::runtime_error("Failed to join meeting: " + std::to_string(error));
    }
}

void ZoomBot::startRecording() {
    if (is_recording_) return;
    
    std::cout << "RECORDING_STARTED" << std::endl;
    is_recording_ = true;
    
    // 録画開始の実装
    // 実際のSDKの録画APIを使用
    auto recording_ctrl = meeting_service_->GetMeetingRecordingController();
    if (recording_ctrl) {
        recording_ctrl->StartRawRecording();
    }
}

void ZoomBot::stopRecording() {
    if (!is_recording_) return;
    
    std::cout << "RECORDING_STOPPED" << std::endl;
    is_recording_ = false;
    
    // 録画停止の実装
    auto recording_ctrl = meeting_service_->GetMeetingRecordingController();
    if (recording_ctrl) {
        recording_ctrl->StopRawRecording();
    }
}

void ZoomBot::onAuthenticationReturn(AuthResult result) {
    if (result == AUTHRET_SUCCESS) {
        std::cout << "AUTHENTICATION_SUCCESS" << std::endl;
        joinMeeting();
    } else {
        std::cout << "AUTHENTICATION_FAILED" << std::endl;
        throw std::runtime_error("Authentication failed: " + std::to_string(result));
    }
}

void ZoomBot::onLoginRet(PluginLoginResult result) {
    // 実装不要
}

void ZoomBot::onLogoutRet(PluginLogoutResult result) {
    // 実装不要
}

void ZoomBot::onMeetingStatusChanged(MeetingStatus status, int result) {
    switch (status) {
        case MEETING_STATUS_CONNECTING:
            std::cout << "MEETING_CONNECTING" << std::endl;
            break;
        case MEETING_STATUS_INMEETING:
            std::cout << "MEETING_JOINED" << std::endl;
            startRecording();
            break;
        case MEETING_STATUS_ENDED:
            std::cout << "MEETING_ENDED" << std::endl;
            stop();
            break;
        case MEETING_STATUS_FAILED:
            std::cout << "MEETING_FAILED" << std::endl;
            throw std::runtime_error("Meeting failed: " + std::to_string(result));
            break;
        default:
            break;
    }
}

void ZoomBot::onMeetingStatisticsWarningNotification(StatisticsWarningType type) {
    // 実装不要
}

void ZoomBot::onMeetingParameterNotification(const MeetingParameter* meeting_param) {
    // 実装不要
}

void ZoomBot::saveAudioData(const char* data, size_t size) {
    std::string audio_path = output_path_ + "/audio.wav";
    std::ofstream audio_file(audio_path, std::ios::binary | std::ios::app);
    
    if (audio_file.is_open()) {
        audio_file.write(data, size);
        audio_file.close();
        std::cout << "AUDIO_DATA_SAVED: " << size << " bytes" << std::endl;
    }
}
EOF
```

### ビルド設定
```bash
# JSON ライブラリインストール
sudo apt install -y libjsoncpp-dev

# ビルドディレクトリ作成
mkdir -p build
cd build

# CMake実行
cmake ..

# ビルド
make -j$(nproc)

# 実行ファイル確認
ls -la zoom-bot
```

## 7. サービス化とシステム設定

### systemd サービス作成
```bash
# Zoom Bot Server サービス
sudo tee /etc/systemd/system/zoom-bot-server.service > /dev/null << 'EOF'
[Unit]
Description=Zoom Meeting Bot Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/project/zoom_bot_server
ExecStartPre=/home/ubuntu/setup-audio.sh
ExecStart=/usr/bin/node server.js
Environment=NODE_ENV=production
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Django アプリケーションサービス
sudo tee /etc/systemd/system/voice-picker-api.service > /dev/null << 'EOF'
[Unit]
Description=Voice Picker API (Django)
After=network.target mysql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/project/macching_app
ExecStart=/path/to/project/macching_app/venv/bin/python manage.py runserver 0.0.0.0:8000
Environment=DJANGO_SETTINGS_MODULE=config.settings
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# サービス有効化
sudo systemctl daemon-reload
sudo systemctl enable zoom-bot-server
sudo systemctl enable voice-picker-api
```

### セキュリティ設定
```bash
# UFW ファイアウォール設定
sudo ufw allow 8000  # Django API
sudo ufw allow 4000  # Zoom Bot Server
sudo ufw allow 22    # SSH
sudo ufw --force enable

# ディレクトリ権限設定
sudo chown -R $USER:$USER /path/to/project
chmod 755 /path/to/project
```

## 8. 動作確認

### 手動テスト
```bash
# 音声セットアップ
./setup-audio.sh

# Zoom Bot Server 起動
cd zoom_bot_server
node server.js

# 別ターミナルで Django 起動
cd macching_app
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# API テスト
curl -X POST http://localhost:4000/api/zoom/parse-url \
  -H "Content-Type: application/json" \
  -d '{"meetingUrl": "https://zoom.us/j/123456789"}'
```

### サービス起動
```bash
# サービス開始
sudo systemctl start zoom-bot-server
sudo systemctl start voice-picker-api

# ステータス確認
sudo systemctl status zoom-bot-server
sudo systemctl status voice-picker-api

# ログ確認
sudo journalctl -u zoom-bot-server -f
sudo journalctl -u voice-picker-api -f
```

## 9. トラブルシューティング

### よくある問題と解決方法

#### 1. 音声デバイスエラー
```bash
# PulseAudioの再設定
sudo systemctl restart pulseaudio
./setup-audio.sh

# 音声デバイス確認
pactl list sinks
pactl list sources
```

#### 2. SDK初期化エラー
```bash
# ライブラリパス確認
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
sudo ldconfig

# 権限確認
ls -la ~/.config.us/zoomus.conf
```

#### 3. メモリ不足
```bash
# スワップファイル作成
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永続化
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 10. 本番環境運用

### 監視設定
```bash
# ログローテーション
sudo tee /etc/logrotate.d/zoom-bot << 'EOF'
/var/log/zoom-bot/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# プロセス監視
sudo apt install -y htop iotop
```

### バックアップ設定
```bash
# 録画ファイルバックアップ
sudo tee /etc/cron.daily/backup-recordings << 'EOF'
#!/bin/bash
rsync -av /var/recordings/ /backup/recordings/
find /backup/recordings -name "*.wav" -mtime +30 -delete
EOF

sudo chmod +x /etc/cron.daily/backup-recordings
```

これでUbuntu Linux環境でのZoom Meeting SDK セットアップが完了です。