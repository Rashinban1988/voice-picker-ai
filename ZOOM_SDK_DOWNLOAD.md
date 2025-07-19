# Zoom Meeting SDK ダウンロード手順（Ubuntu本番環境）

## 📱 Zoom開発者アカウントでの取得手順

### 1. Zoom開発者ポータルにアクセス
```bash
# ブラウザで以下にアクセス
https://developers.zoom.us/
```

### 2. アカウント作成・ログイン
- Zoom開発者アカウントを作成またはログイン
- 「Build App」ボタンをクリック

### 3. Meeting SDKアプリを作成
- アプリタイプで「Meeting SDK」を選択
- アプリ名を入力（例：Voice Picker Recording Bot）
- 必要情報を入力して作成

### 4. SDK認証情報を取得
- 作成したアプリの設定画面で以下を取得：
  - **SDK Key**
  - **SDK Secret**

### 5. SDKファイルのダウンロード
- 左メニューの「Features」→ 「Embed」
- 「Meeting SDK」トグルを有効化
- 「Download SDK」ボタンをクリック
- **Linux SDK**を選択してダウンロード

## 🔄 代替方法：Zoom Marketplaceから取得

### 方法1: Zoom Marketplace経由
```bash
# ブラウザでアクセス
https://marketplace.zoom.us/

# Meeting SDK for Linuxを検索
# ダウンロードページからLinux版SDKを取得
```

### 方法2: 公式ドキュメントページ
```bash
# 公式ダウンロードページ
https://developers.zoom.us/docs/meeting-sdk/linux/get-started/download/
```

## 📦 Ubuntu環境でのセットアップ

ダウンロード後、以下の手順でセットアップ：

```bash
# プロジェクトディレクトリに移動
cd ~/voice-picker-ai/macching_app/zoom_bot_server/zoom_meeting_sdk

# ダウンロードしたファイルを配置
# (ブラウザでダウンロードしたファイルを/home/vpi/Downloads/から移動)
cp ~/Downloads/zoom-meeting-sdk-linux*.tar.xz ./

# 解凍
tar -xf zoom-meeting-sdk-linux*.tar.xz --strip-components=1

# 重要なファイルの確認
ls -la libmeetingsdk.so
ls -la h/
ls -la qt_libs/
```

## 📝 環境変数設定

```bash
# .envファイルを編集
nano ~/voice-picker-ai/macching_app/.env

# 以下を追加/更新
ZOOM_MEETING_SDK_KEY=your_sdk_key_here
ZOOM_MEETING_SDK_SECRET=your_sdk_secret_here
PRODUCTION=true
NODE_ENV=production
```

## ⚡ 最新バージョン情報（2025年）

- **推奨バージョン**: 6.3.0以降
- **チェンジログ**: https://developers.zoom.us/changelog/meeting-sdk/linux/
- **API リファレンス**: https://marketplacefront.zoom.us/sdk/meeting/linux/

## 🔧 トラブルシューティング

### ダウンロードできない場合
1. **Zoom開発者アカウントの確認**
   - Pro以上のZoomアカウントが必要な場合があります

2. **アプリの承認状況確認**
   - Meeting SDKアプリが「Development」から「Production」に移行が必要な場合があります

3. **代替取得方法**
   - 別のZoom開発者アカウントで試行
   - Zoomサポートに問い合わせ

### ファイルが見つからない場合
```bash
# 解凍後のファイル構造確認
find . -name "*.so" -type f
find . -name "libmeetingsdk*" -type f

# 権限設定
chmod +x libmeetingsdk.so
```

## 🎯 完了後の確認

```bash
# SDKファイルの確認
ldd libmeetingsdk.so | head -10

# Docker環境での確認
cd ~/voice-picker-ai/macching_app
docker-compose build zoom_bot_server
docker-compose up -d
docker-compose logs zoom_bot_server | grep "SDK"
```

SDKが正常にダウンロード・配置されたら、実際のZoom会議音声キャプチャが可能になります！