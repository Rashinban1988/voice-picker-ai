#!/bin/bash

# ホストマシンでPulseAudioを設定するスクリプト
# Ubuntu環境でDockerコンテナからPulseAudioにアクセスできるようにする

echo "Setting up PulseAudio for Docker container access..."

# 1. PulseAudioのTCP接続を有効化
echo "Enabling PulseAudio network access..."
pactl load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12

# 2. 仮想シンクを作成
echo "Creating virtual sink for Zoom recording..."
pactl unload-module module-null-sink 2>/dev/null
pactl load-module module-null-sink sink_name=zoom_recorder sink_properties=device.description="Zoom_Recorder"

# 3. モニターソースを作成
echo "Creating monitor source..."
pactl set-default-sink zoom_recorder

# 4. Cookie共有のためのディレクトリ権限設定
echo "Setting up PulseAudio cookie permissions..."
if [ -f ~/.config/pulse/cookie ]; then
    chmod 644 ~/.config/pulse/cookie
fi

# 5. 環境変数を表示
echo ""
echo "PulseAudio setup complete!"
echo ""
echo "To use in Docker, add these to your docker-compose.yml:"
echo "  environment:"
echo "    - PULSE_SERVER=tcp:host.docker.internal:4713"
echo "  extra_hosts:"
echo "    - 'host.docker.internal:host-gateway'"
echo ""
echo "In Zoom:"
echo "  1. Go to Settings > Audio"
echo "  2. Set Speaker to 'Zoom_Recorder'"
echo "  3. The audio will be captured by the bot"