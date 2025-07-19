#!/bin/bash

# PulseAudio仮想オーディオデバイスのセットアップ
echo "Setting up virtual audio devices for Zoom recording..."

# 1. 仮想シンクを作成（Zoomの音声出力先）
pactl load-module module-null-sink sink_name=zoom_sink sink_properties=device.description="Zoom_Virtual_Sink"

# 2. モニターソースから録音できるようにする
pactl load-module module-loopback source=zoom_sink.monitor sink=@DEFAULT_SINK@

# 3. 録音用の仮想ソースを作成
pactl load-module module-virtual-source source_name=zoom_recorder master=zoom_sink.monitor

echo "Virtual audio devices created."
echo ""
echo "To use:"
echo "1. In Zoom settings, set speaker to 'Zoom_Virtual_Sink'"
echo "2. Record from 'zoom_recorder' source"
echo ""
echo "To record:"
echo "parecord -d zoom_recorder --file-format=wav output.wav"