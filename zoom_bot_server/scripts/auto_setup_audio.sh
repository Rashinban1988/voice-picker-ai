#!/bin/bash

# 自動音声設定スクリプト
echo "🎵 Zoom音声キャプチャの自動設定を開始..."

# 1. 既存の仮想シンクを削除
echo "📤 既存設定をクリーンアップ..."
pactl unload-module module-null-sink 2>/dev/null

# 2. 新しい仮想シンクを作成
echo "🔧 仮想オーディオデバイスを作成..."
MODULE_ID=$(pactl load-module module-null-sink sink_name=zoom_recorder sink_properties=device.description="Zoom_Audio_Recorder")

if [ $? -eq 0 ]; then
    echo "✅ 仮想シンク作成成功 (Module ID: $MODULE_ID)"
else
    echo "❌ 仮想シンク作成失敗"
    exit 1
fi

# 3. ループバックを作成（音声が聞こえるように）
echo "🔄 オーディオループバックを設定..."
LOOPBACK_ID=$(pactl load-module module-loopback source=zoom_recorder.monitor sink=@DEFAULT_SINK@ latency_msec=1)

if [ $? -eq 0 ]; then
    echo "✅ ループバック設定成功 (Module ID: $LOOPBACK_ID)"
else
    echo "⚠️  ループバック設定失敗（音声が聞こえない可能性があります）"
fi

# 4. 利用可能なオーディオデバイスを表示
echo ""
echo "📋 現在利用可能なオーディオデバイス："
pactl list sinks short | grep -E "(zoom_recorder|analog|hdmi)"

echo ""
echo "🎯 次のステップ："
echo "1. Zoomアプリを開く"
echo "2. 設定 → オーディオ → スピーカー"
echo "3. 'Zoom_Audio_Recorder' を選択"
echo "4. 録画を開始"

echo ""
echo "🔧 録画開始コマンド例："
echo "curl -X POST http://localhost:4000/api/zoom/start-recording \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"meetingUrl\": \"YOUR_ZOOM_URL\", \"userName\": \"録画ボット\"}'"

echo ""
echo "🧹 設定をリセットする場合："
echo "pactl unload-module $MODULE_ID"
echo "pactl unload-module $LOOPBACK_ID"