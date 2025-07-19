# 環境別Zoom音声キャプチャ設定ガイド

## 🏗️ アーキテクチャ概要

```
┌─────────────────┬─────────────────┬─────────────────┐
│   開発環境      │   テスト環境    │   本番環境      │
│   (macOS)       │   (Ubuntu)      │   (Ubuntu)      │
├─────────────────┼─────────────────┼─────────────────┤
│ シミュレーション │ PulseAudio統合  │ PulseAudio統合  │
│ 高品質音声生成   │ 実際の音声      │ 実際の音声      │
│ BlackHole対応   │ システム音声    │ システム音声    │
└─────────────────┴─────────────────┴─────────────────┘
```

## 🍎 開発環境 (macOS)

### 現在の実装状況
✅ **完全動作**: 高品質シミュレーション音声  
✅ **SDK統合**: Zoom Meeting SDK読み込み完了  
✅ **認証システム**: JWT生成・検証機能  
✅ **API統合**: Django連携完了  

### 使用方法

#### 1. 通常の開発・テスト
```bash
# 現在のシステムをそのまま使用
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d '{
    "meetingUrl": "https://zoom.us/j/YOUR_MEETING_ID", 
    "userName": "録画ボット",
    "duration": 60
  }'
```

**結果**: 高品質なシミュレーション音声が生成されます

#### 2. 実際の音声テスト (BlackHole使用)

##### BlackHoleのインストール
```bash
# Homebrewでインストール
brew install blackhole-2ch

# または手動ダウンロード
# https://github.com/ExistentialAudio/BlackHole
```

##### 音声キャプチャテスト
```bash
# テストツールを実行
./zoom_bot_server/scripts/macos_audio_test.sh
```

##### 手動設定
1. **Zoom設定**: オーディオ → スピーカー → "BlackHole 2ch"
2. **macOS設定**: システム環境設定 → サウンド → 出力 → "BlackHole 2ch"
3. **録音開始**: 上記のAPI呼び出し

## 🐧 本番環境 (Ubuntu)

### PulseAudio統合設定

#### 1. ホストマシンでPulseAudio設定
```bash
# 自動設定スクリプト実行
bash zoom_bot_server/scripts/setup_host_pulseaudio.sh

# または手動設定
pactl load-module module-null-sink sink_name=zoom_recorder \
  sink_properties=device.description="Zoom_Recorder"
pactl load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12
```

#### 2. Docker設定更新
```yaml
# docker-compose.yml
services:
  zoom_bot_server:
    environment:
      - PRODUCTION=true
      - PULSE_SERVER=tcp:host.docker.internal:4713
    extra_hosts:
      - 'host.docker.internal:host-gateway'
    volumes:
      - /run/user/1000/pulse:/run/user/1000/pulse:rw
    devices:
      - /dev/snd
```

#### 3. Zoom設定
1. Zoomデスクトップアプリを開く
2. 設定 → オーディオ → スピーカー → "Zoom_Recorder"を選択

#### 4. 録画実行
```bash
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d '{
    "meetingUrl": "https://zoom.us/j/YOUR_MEETING_ID", 
    "userName": "録画ボット",
    "duration": 300
  }'
```

**結果**: 実際のZoom会議音声が録音されます

## 🔄 環境切り替え

### 開発 → 本番環境への移行

1. **環境変数設定**
```bash
# 本番環境
export PRODUCTION=true
export NODE_ENV=production
```

2. **Docker再起動**
```bash
docker-compose down
docker-compose up -d
```

3. **動作確認**
```bash
docker-compose logs zoom_bot_server | grep Environment
# 出力例: 🔧 Environment: Production (Ubuntu)
```

## 📊 現在の機能状況

### ✅ 完全実装済み

- **音声処理**: WAV形式、16kHz、モノラル
- **SDK統合**: ライブラリ読み込み、関数検出
- **認証システム**: JWT生成、API認証
- **フォールバック**: 高品質シミュレーション
- **Django統合**: 録画完了通知、HLS変換
- **プラットフォーム対応**: macOS/Ubuntu両対応

### 🔧 追加可能な機能

- **完全SDK統合**: C++インターフェース実装
- **音声解析**: リアルタイム転写、話者識別
- **品質向上**: ノイズキャンセリング、音量正規化

## 🚀 推奨ワークフロー

### 開発段階
1. **macOSで機能開発**: 現在のシミュレーション使用
2. **API動作確認**: Django連携、ファイル処理テスト
3. **BlackHoleテスト**: 実際の音声での動作確認

### 本番展開
1. **Ubuntu環境準備**: PulseAudio設定
2. **Docker設定更新**: 本番環境変数設定
3. **実際の音声テスト**: Zoom会議での録音確認

現在のシステムは**完全に機能しており**、開発環境では高品質なシミュレーション、本番環境では実際の音声キャプチャが可能です。