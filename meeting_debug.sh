#!/bin/bash

# 会議の存在確認とデバッグ

MEETING_ID="88097705538"
PASSWORD="9LyK2J"

echo "=== 会議診断 ==="
echo "会議ID: $MEETING_ID"
echo "パスワード: $PASSWORD"
echo ""

# 1. 会議URLの妥当性確認
echo "1. URL解析テスト..."
curl -X POST http://localhost:4000/api/zoom/parse-url \
  -H "Content-Type: application/json" \
  -d "{\"meetingUrl\": \"https://zoom.us/j/$MEETING_ID?pwd=$PASSWORD\"}"

echo ""
echo ""

# 2. SDK状態確認
echo "2. SDK状態確認..."
curl -s http://localhost:4000/api/zoom/sdk-status | jq .

echo ""
echo ""

# 3. 詳細ログ確認
echo "3. 最新のボットログ..."
docker logs macching_app-zoom_bot_server-1 --tail 20

echo ""
echo "=== 診断完了 ==="
echo ""
echo "✅ 確認項目："
echo "- Zoomアプリで会議が開始されているか"
echo "- 待機室がオフになっているか"  
echo "- 参加時の認証が不要になっているか"
echo "- ホストとして参加しているか"