# テスト用Zoomミーティング作成ガイド

## 1. 最も簡単な方法：インスタントミーティング

### ステップ1: Zoomでミーティング開始
1. Zoomアプリまたはブラウザで [zoom.us](https://zoom.us) にアクセス
2. 「新規ミーティング」をクリック
3. 「コンピューターでオーディオに参加」を選択

### ステップ2: ミーティング情報取得
1. 画面下部の「参加者」アイコンをクリック
2. 「招待」をクリック
3. 「招待のコピー」からミーティング情報をコピー

例：
```
トピック: クイックミーティング
時間: 2024年1月15日 10:00 AM

Zoomミーティングに参加する
https://zoom.us/j/1234567890?pwd=abcdefgh

ミーティングID: 123 456 7890
パスコード: abcdefgh
```

### ステップ3: Voice Picker AIでテスト
```bash
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d '{
    "meetingUrl": "https://zoom.us/j/1234567890?pwd=abcdefgh",
    "userName": "VoicePickerBot",
    "uploadedFileId": "test-instant-meeting"
  }'
```

## 2. 代替方法：パーソナルミーティングルーム（PMR）

### Zoomアカウントでのセットアップ
1. [zoom.us](https://zoom.us) にログイン
2. 「プロフィール」→「パーソナルミーティングID」
3. 「パーソナルミーティングIDを使用」を有効化
4. 固定のパスワードを設定

### 常時利用可能なURL
```
https://zoom.us/j/YOUR_PMI?pwd=YOUR_PASSWORD
```

## 3. 開発者向け：Zoom SDK サンプル

### 開発者アカウント作成
1. [marketplace.zoom.us](https://marketplace.zoom.us) にアクセス
2. 「Develop」→「Build App」
3. 「Meeting SDK」を選択
4. サンプルアプリをダウンロード

### サンプルミーティング
- Zoom公式のサンプルミーティングIDが提供される場合があります
- 開発者コミュニティで共有されるテスト用ミーティング

## 4. 注意事項

### セキュリティ設定
- **待機室を無効化**：設定→会議→待機室をオフ
- **パスワードをオプション化**：参加にパスワードを要求しない
- **認証を無効化**：サインインを必要としない

### テスト用の最適設定
```json
{
  "meetingUrl": "https://zoom.us/j/YOUR_MEETING_ID?pwd=YOUR_PASSWORD",
  "userName": "VoicePickerBot",
  "uploadedFileId": "test-recording-001"
}
```

## 5. デバッグ情報

### ミーティングの状態確認
```bash
# ミーティング解析
curl -X POST http://localhost:4000/api/zoom/parse-url \
  -H "Content-Type: application/json" \
  -d '{"meetingUrl": "https://zoom.us/j/YOUR_MEETING_ID?pwd=YOUR_PASSWORD"}'

# 録画状態確認
curl http://localhost:4000/api/zoom/active-recordings
```

### よくある問題と解決方法
1. **"Meeting not found"**: ミーティングが開始されていない
2. **"Authentication failed"**: パスワードが間違っている
3. **"Permission denied"**: 待機室が有効になっている

## 6. 自動テスト用スクリプト

今すぐテストする場合は、以下のスクリプトを実行してください：

```bash
# 即座にテスト用ミーティングを作成
echo "1. Zoomアプリで「新規ミーティング」を開始してください"
echo "2. ミーティングIDとパスワードを入力してください"
read -p "ミーティングID: " MEETING_ID
read -p "パスワード: " PASSWORD

# 録画開始
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d "{
    \"meetingUrl\": \"https://zoom.us/j/$MEETING_ID?pwd=$PASSWORD\",
    \"userName\": \"VoicePickerBot\",
    \"uploadedFileId\": \"test-$(date +%s)\"
  }"
```