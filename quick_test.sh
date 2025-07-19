#!/bin/bash

# クイックテストスクリプト
echo "🎯 Voice Picker AI - Zoomミーティング録画テスト"
echo ""

# テスト用の一般的なミーティングIDフォーマット
TEST_MEETING_IDS=(
    "12345678901"  # 11桁（高成功率）
    "123456789"    # 9桁（標準）
    "1234567890"   # 10桁（標準）
)

echo "📝 利用可能なテストオプション："
echo "1. 実際のZoomミーティング（推奨）"
echo "2. シミュレーションテスト"
echo "3. 既存のテスト用ミーティングID"
echo ""

read -p "選択してください (1-3): " choice

case $choice in
    1)
        echo "📋 実際のZoomミーティングでテスト"
        echo "1. Zoomアプリで「新規ミーティング」を開始"
        echo "2. ミーティング情報をコピー"
        echo ""
        read -p "ミーティングID（数字のみ）: " MEETING_ID
        read -p "パスワード（オプション）: " PASSWORD
        
        if [ -z "$PASSWORD" ]; then
            MEETING_URL="$MEETING_ID"
        else
            MEETING_URL="https://zoom.us/j/$MEETING_ID?pwd=$PASSWORD"
        fi
        ;;
    2)
        echo "🔄 シミュレーションテストを実行"
        MEETING_ID="12345678901"
        MEETING_URL="https://zoom.us/j/$MEETING_ID?pwd=test123"
        ;;
    3)
        echo "📌 既存のテスト用ミーティングID"
        echo "以下のIDから選択："
        for i in "${!TEST_MEETING_IDS[@]}"; do
            echo "$((i+1)). ${TEST_MEETING_IDS[$i]}"
        done
        read -p "選択 (1-${#TEST_MEETING_IDS[@]}): " id_choice
        MEETING_ID="${TEST_MEETING_IDS[$((id_choice-1))]}"
        MEETING_URL="https://zoom.us/j/$MEETING_ID?pwd=test123"
        ;;
    *)
        echo "❌ 無効な選択です"
        exit 1
        ;;
esac

echo ""
echo "🚀 録画開始..."
echo "ミーティングURL: $MEETING_URL"
echo ""

# 録画開始
RESPONSE=$(curl -s -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d "{
    \"meetingUrl\": \"$MEETING_URL\",
    \"userName\": \"VoicePickerBot\",
    \"uploadedFileId\": \"test-$(date +%s)\"
  }")

echo "📊 レスポンス:"
echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"

# セッションIDを抽出
SESSION_ID=$(echo "$RESPONSE" | jq -r '.sessionId' 2>/dev/null)

if [ "$SESSION_ID" != "null" ] && [ -n "$SESSION_ID" ]; then
    echo ""
    echo "✅ 録画開始成功！"
    echo "📍 セッションID: $SESSION_ID"
    echo ""
    echo "⏱️  30秒後に録画状態を確認します..."
    sleep 30
    
    echo "📈 録画状態確認:"
    curl -s http://localhost:4000/api/zoom/active-recordings | jq . 2>/dev/null || curl -s http://localhost:4000/api/zoom/active-recordings
    
    echo ""
    echo "🔧 利用可能なコマンド:"
    echo "# 録画停止"
    echo "curl -X POST http://localhost:4000/api/zoom/stop-recording -H \"Content-Type: application/json\" -d '{\"sessionId\": \"$SESSION_ID\"}'"
    echo ""
    echo "# ログ確認"
    echo "docker logs macching_app-zoom_bot_server-1 --tail 20"
else
    echo "❌ 録画開始に失敗しました"
    echo "🔍 ログを確認してください:"
    echo "docker logs macching_app-zoom_bot_server-1 --tail 10"
fi

echo ""
echo "📚 詳細なテスト手順は create_test_meeting.md を参照してください"