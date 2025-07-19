#!/bin/bash

# Zoom Headless Recorder for Ubuntu
# 仮想ディスプレイでZoomクライアントを実行し、音声をキャプチャ

MEETING_URL=$1
OUTPUT_FILE=$2
DISPLAY_NUM=99

if [ -z "$MEETING_URL" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: $0 <zoom_meeting_url> <output.wav>"
    exit 1
fi

echo "Starting headless Zoom recorder..."

# 1. 仮想ディスプレイを開始
echo "Starting virtual display..."
Xvfb :$DISPLAY_NUM -screen 0 1280x720x24 &
XVFB_PID=$!
export DISPLAY=:$DISPLAY_NUM

# 2. PulseAudioダミーデバイスを作成
echo "Creating virtual audio devices..."
pactl load-module module-null-sink sink_name=zoom_recorder
pactl set-default-sink zoom_recorder
pactl set-default-source zoom_recorder.monitor

# 3. 音声録音を開始（バックグラウンド）
echo "Starting audio recording..."
parec -d zoom_recorder.monitor --file-format=wav --format=s16le --rate=16000 --channels=1 > "$OUTPUT_FILE" &
RECORDING_PID=$!

# 4. Zoomクライアントを起動
echo "Starting Zoom client..."
# 注: zoom-clientパッケージがインストールされている必要があります
# sudo snap install zoom-client または sudo apt install zoom
zoom --url="$MEETING_URL" &
ZOOM_PID=$!

# 5. 録音を継続
echo "Recording... Press Ctrl+C to stop"
trap "kill $RECORDING_PID $ZOOM_PID $XVFB_PID; exit" INT TERM

# 録音を継続
wait $RECORDING_PID

echo "Recording completed: $OUTPUT_FILE"