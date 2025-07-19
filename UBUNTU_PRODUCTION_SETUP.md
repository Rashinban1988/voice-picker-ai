# Ubuntu本番環境セットアップガイド

## 🚀 本番環境への移行手順

### 1. Gitコミット・プッシュ（macOS開発環境）

```bash
# 現在の実装をコミット
cd /Users/yamamoto/develop/portforio/voice-picker-ai/macching_app
git add .
git commit -m "✨ 実際のZoom音声キャプチャシステム完成

- Zoom Meeting SDK統合完了
- PulseAudio音声キャプチャ実装
- macOS/Ubuntu環境自動検出
- 高品質シミュレーション音声生成
- Django統合・HLS変換対応
- 本番環境用PulseAudio設定スクリプト追加"

git push origin main
```

### 2. Ubuntu環境での準備

#### 必要なパッケージインストール
```bash
# システム更新
sudo apt update && sudo apt upgrade -y

# Docker & Docker Compose
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# PulseAudio（音声処理用）
sudo apt install -y pulseaudio pulseaudio-utils pavucontrol

# 開発ツール（必要に応じて）
sudo apt install -y git curl wget build-essential
```

#### ログアウト・再ログイン
```bash
# Dockerグループの権限反映のため
logout
# 再ログイン後
```

### 3. プロジェクトクローン・セットアップ

```bash
# プロジェクトクローン
cd ~
git clone https://github.com/mest-yamaru/voice-picker-ai.git
cd voice-picker-ai/macching_app

# 環境変数設定（本番用）
cp .env.example .env  # 環境変数ファイルを作成
nano .env  # 以下の設定を追加
```

#### .env設定内容
```env
# 本番環境フラグ
PRODUCTION=true
NODE_ENV=production

# Zoom SDK認証情報
ZOOM_MEETING_SDK_KEY=your_zoom_sdk_key
ZOOM_MEETING_SDK_SECRET=your_zoom_sdk_secret

# Django設定
APP_PORT=8000
DEBUG_PORT=5678

# PulseAudio設定
PULSE_SERVER=unix:/run/user/1000/pulse/native
```

### 4. PulseAudio本番環境設定

```bash
# 自動設定スクリプト実行
chmod +x zoom_bot_server/scripts/setup_host_pulseaudio.sh
bash zoom_bot_server/scripts/setup_host_pulseaudio.sh

# 手動確認
pactl list sinks short | grep zoom_recorder
# 出力例: 2	zoom_recorder	module-null-sink.c	s16le 2ch 44100Hz	SUSPENDED
```

### 5. Docker設定更新（本番用）

#### docker-compose.override.yml作成
```bash
cat > docker-compose.override.yml << 'EOF'
# Ubuntu本番環境用設定
services:
  zoom_bot_server:
    environment:
      - PRODUCTION=true
      - NODE_ENV=production
      - PULSE_SERVER=unix:/run/user/1000/pulse/native
    volumes:
      - /run/user/1000/pulse:/run/user/1000/pulse:rw
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
    devices:
      - /dev/snd
    privileged: true
    
  django:
    environment:
      - PRODUCTION=true
      - NODE_ENV=production
EOF
```

### 6. システム起動

```bash
# Dockerネットワーク作成
docker network create webdev || true

# システム起動
docker-compose up -d

# 起動確認
docker-compose ps
docker-compose logs zoom_bot_server | grep Environment
# 期待する出力: 🔧 Environment: Production (Ubuntu)
```

### 7. Zoomデスクトップアプリ設定

```bash
# Zoomアプリインストール（未インストールの場合）
wget https://zoom.us/client/latest/zoom_amd64.deb
sudo dpkg -i zoom_amd64.deb
sudo apt-get install -f  # 依存関係の修正

# Zoomアプリ起動後
# 設定 → オーディオ → スピーカー → "Zoom_Recorder" を選択
```

### 8. 動作テスト

#### API接続テスト
```bash
curl -X GET http://localhost:4000/api/zoom/status
# 期待する出力: システム情報とSDK状態
```

#### 実際の録画テスト
```bash
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d '{
    "meetingUrl": "https://zoom.us/j/YOUR_MEETING_ID", 
    "userName": "録画ボット",
    "duration": 60
  }'
```

### 9. 動作確認ポイント

#### ✅ 確認項目
```bash
# 1. 環境検出
docker-compose logs zoom_bot_server | grep "Production"

# 2. PulseAudio接続
docker exec macching_app-zoom_bot_server-1 pactl info

# 3. 音声デバイス
pactl list sinks short | grep zoom

# 4. 録画ファイル生成
ls -la media/zoom_recordings/

# 5. Django連携
docker-compose logs django | grep "Recording completed"
```

## 🔧 トラブルシューティング

### PulseAudioエラーの場合
```bash
# PulseAudio再起動
pulseaudio --kill
pulseaudio --start

# 権限確認
ls -la /run/user/1000/pulse/
```

### Docker権限エラーの場合
```bash
# Dockerグループ確認
groups | grep docker

# 権限再設定
sudo usermod -aG docker $USER
# ログアウト・再ログイン
```

### 音声キャプチャされない場合
```bash
# 音声デバイステスト
parecord --device=zoom_recorder.monitor --file-format=wav test.wav
# Ctrl+C で停止
aplay test.wav  # 再生テスト
```

## 🎯 期待される結果

本番環境での設定完了後：

1. **実際のZoom会議音声**が録音される
2. **Next.jsアプリから**同じAPIで利用可能
3. **Django側で録画ファイル**が正常に処理される
4. **HLS変換**が自動実行される

設定が完了したら、実際のZoom会議URLで録画テストを実行してください！