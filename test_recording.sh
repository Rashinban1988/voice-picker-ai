#!/bin/bash

# Zoom録画テストスクリプト

echo "Zoom録画テストを開始します..."

# ミーティングIDとパスワードを入力
read -p "ミーティングID（数字のみ）: " MEETING_ID
read -p "パスコード（オプション）: " PASSWORD

# URLを構築
if [ -z "$PASSWORD" ]; then
    MEETING_URL="$MEETING_ID"
else
    MEETING_URL="https://zoom.us/j/$MEETING_ID?pwd=$PASSWORD"
fi

echo "録画を開始します: $MEETING_URL"

# 録画開始
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d "{
    \"meetingUrl\": \"$MEETING_URL\",
    \"userName\": \"VoicePickerBot\",
    \"uploadedFileId\": \"test-$(date +%s)\"
  }"

echo ""
echo "録画状態を確認するには："
echo "curl http://localhost:4000/api/zoom/active-recordings"