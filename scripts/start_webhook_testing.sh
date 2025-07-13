#!/bin/bash

# Webhook統合テスト環境開始スクリプト
# ngrokとStripe CLIを使用してローカルWebhookテストを実行

echo "🎣 Webhook統合テスト環境を開始しています..."

# 環境変数をエクスポート（設定ファイルのデフォルト値を保証）
export NEXT_JS_HOST="http://localhost"
export NEXT_JS_PORT="3000"

# 1. ngrokの起動確認
echo "📡 ngrokを起動中..."
pkill -f "ngrok http" 2>/dev/null || true
sleep 2

# ngrokを非同期で起動
ngrok http 8000 > /dev/null 2>&1 &
NGROK_PID=$!

# ngrokのAPIが利用可能になるまで待機
echo "⏳ ngrokの起動を待機中..."
for i in {1..30}; do
    if curl -s http://localhost:4040/api/tunnels >/dev/null 2>&1; then
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "❌ ngrokの起動に失敗しました"
        exit 1
    fi
done

# ngrok URLを取得
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys
try:
    import json
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for tunnel in tunnels:
        if tunnel.get('proto') == 'https':
            print(tunnel['public_url'])
            break
except Exception:
    pass
")

if [ -z "$NGROK_URL" ]; then
    echo "❌ ngrok URLの取得に失敗しました"
    kill $NGROK_PID 2>/dev/null || true
    exit 1
fi

echo "✅ ngrok URL: $NGROK_URL"

# .env.testファイルのWebhook URLを更新
if [ -f ".env.test" ]; then
    # Webhook URLを更新
    sed -i.bak "s|STRIPE_WEBHOOK_URL=.*|STRIPE_WEBHOOK_URL=${NGROK_URL}/api/webhook/stripe/|g" .env.test
    echo "📝 .env.testのWebhook URLを更新しました"
fi

# 2. Webhook機能テスト
echo "🧪 Webhook機能テストを実行中..."

# 環境変数ファイルを読み込み
if [ -f ".env.test" ]; then
    export $(cat .env.test | grep -v "^#" | xargs)
fi

# シンプルなWebhookテスト実行
python simple_webhook_test.py

if [ $? -eq 0 ]; then
    echo "✅ Webhook機能テスト成功"
else
    echo "❌ Webhook機能テストに失敗しました"
    kill $NGROK_PID 2>/dev/null || true
    exit 1
fi

# 3. 環境情報表示
echo ""
echo "🌐 ===== Webhook統合テスト環境情報 ====="
echo "📡 ngrok URL: $NGROK_URL"
echo "🔗 Webhook URL: ${NGROK_URL}/api/webhook/stripe/"
echo "📊 ngrok Inspector: http://localhost:4040"
echo ""

echo "✅ Webhook統合テスト環境準備完了！"
echo ""
echo "🎯 次のステップ:"
echo "1. Stripeダッシュボードでテスト用Webhookエンドポイントを設定"
echo "   URL: ${NGROK_URL}/api/webhook/stripe/"
echo "2. 手動でStripe Checkoutや支払いをテストしてWebhookが動作することを確認"
echo ""
echo "🔄 手動テストを実行するには:"
echo "   curl -X POST ${NGROK_URL}/api/webhook/stripe/ \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -H 'Stripe-Signature: test_signature' \\"
echo "        -d '{\"type\": \"checkout.session.completed\"}'"

echo ""
echo "🛑 終了するには Ctrl+C を押してください"
echo "   環境をクリーンアップします..."

# シグナルハンドラーでクリーンアップ
cleanup() {
    echo ""
    echo "🧹 環境をクリーンアップ中..."
    kill $NGROK_PID $DJANGO_PID 2>/dev/null || true
    echo "✅ クリーンアップ完了"
    exit 0
}

trap cleanup SIGINT SIGTERM

# プロセスが終了するまで待機
wait
