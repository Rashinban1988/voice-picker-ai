#!/bin/bash

# macOS開発環境用音声テストツール
echo "🍎 macOS Zoom音声キャプチャテストツール"
echo "============================================"

# BlackHoleの確認
echo "📋 1. BlackHoleデバイスの確認..."
system_profiler SPAudioDataType | grep -i blackhole
if [ $? -eq 0 ]; then
    echo "✅ BlackHoleが検出されました"
else
    echo "❌ BlackHoleが見つかりません"
    echo "💡 インストール方法:"
    echo "   brew install blackhole-2ch"
    echo "   または https://github.com/ExistentialAudio/BlackHole からダウンロード"
fi

echo ""
echo "📋 2. 利用可能な音声デバイス:"
ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep -E "\[AVFoundation.*\] \[.*\]"

echo ""
echo "📝 3. テスト録音の実行 (10秒間):"
echo "   以下のステップを実行してください:"
echo "   1. Zoom設定 → オーディオ → スピーカー → 'BlackHole 2ch' を選択"
echo "   2. システム環境設定 → サウンド → 出力 → 'BlackHole 2ch' を選択"
echo "   3. Zoom会議を開始"
echo "   4. Enterを押してテスト録音を開始"

read -p "準備ができたらEnterを押してください..."

TEST_FILE="/tmp/zoom_audio_test_$(date +%s).wav"
echo "🎵 テスト録音を開始... (10秒間)"

# BlackHoleから音声をキャプチャ
ffmpeg -f avfoundation -i ":BlackHole 2ch" -t 10 -ar 16000 -ac 1 -y "$TEST_FILE" 2>/dev/null

if [ -f "$TEST_FILE" ]; then
    FILE_SIZE=$(stat -f%z "$TEST_FILE" 2>/dev/null || stat -c%s "$TEST_FILE" 2>/dev/null)
    echo "✅ 録音完了: $TEST_FILE"
    echo "📊 ファイルサイズ: $FILE_SIZE bytes"
    
    if [ $FILE_SIZE -gt 1000 ]; then
        echo "🎉 音声が正常にキャプチャされました！"
        echo "🔊 再生テスト:"
        afplay "$TEST_FILE"
    else
        echo "⚠️  音声データが少ないです。設定を確認してください。"
    fi
    
    echo "🗑️  テストファイルを削除しますか? (y/N)"
    read -n 1 cleanup
    if [[ $cleanup =~ ^[Yy]$ ]]; then
        rm "$TEST_FILE"
        echo "削除しました"
    fi
else
    echo "❌ 録音に失敗しました"
fi

echo ""
echo "📚 詳細な設定方法: ./MACOS_ZOOM_AUDIO_CAPTURE.md を参照してください"