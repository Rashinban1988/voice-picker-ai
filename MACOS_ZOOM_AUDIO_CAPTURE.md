# macOS開発環境でのZoom音声キャプチャ

## 現在の状況
- **開発環境**: macOS
- **本番環境**: Ubuntu
- **課題**: macOSでは直接的なPulseAudio統合ができない

## macOS用の実装方法

### 方法1: BlackHole + ffmpeg（推奨）

#### 1. BlackHoleをインストール
```bash
# Homebrewでインストール
brew install blackhole-2ch

# または手動ダウンロード
# https://github.com/ExistentialAudio/BlackHole
```

#### 2. macOS用音声キャプチャスクリプトを作成
```bash
# zoom_bot_server/scripts/macos_audio_capture.sh
#!/bin/bash

MEETING_ID=$1
DURATION=${2:-300}
OUTPUT_FILE="/app/media/zoom_recordings/$MEETING_ID/audio.wav"

echo "🎵 macOS音声キャプチャを開始..."
echo "📋 手順:"
echo "1. Zoom設定 → オーディオ → スピーカー → 'BlackHole 2ch' を選択"
echo "2. システム環境設定 → サウンド → 出力 → 'BlackHole 2ch' を選択"
echo "3. 会議を開始してください"

# BlackHoleから音声をキャプチャ
ffmpeg -f avfoundation -i ":BlackHole 2ch" -t $DURATION -ar 16000 -ac 1 -y "$OUTPUT_FILE"
```

### 方法2: システム音声を直接キャプチャ

#### macOS用C++ボット実装の更新

```cpp
// hybrid_zoom_bot.cpp に追加
#ifdef __APPLE__
bool startMacOSAudioCapture() {
    std::cout << "MACOS: Starting system audio capture..." << std::endl;
    
    // macOS用のAudioUnit/CoreAudioを使用
    // 簡易実装：ffmpegを使用
    std::string command = "ffmpeg -f avfoundation -i \":0\" -t " + 
                         std::to_string(recordingDuration) + 
                         " -ar 16000 -ac 1 -y " + outputPath;
    
    int result = system(command.c_str());
    return result == 0;
}
#endif
```

### 方法3: Docker内での音声処理（現在の実装を活用）

#### macOS用docker-compose設定
```yaml
# docker-compose.override.yml (macOS用)
services:
  zoom_bot_server:
    volumes:
      - ./zoom_bot_server:/app
      - ./media/zoom_recordings:/app/media/zoom_recordings
      - ~/Desktop/zoom_audio_input:/app/audio_input  # macOS音声ファイル共有用
    environment:
      - MACOS_DEVELOPMENT=true
      - AUDIO_SOURCE=file  # ファイルベースの音声処理
```

### 方法4: 開発用シミュレーション強化（即座に実装可能）

現在のシステムを活用して、開発環境では高品質なシミュレーションを使用し、本番環境では実際の音声をキャプチャする設定：

```javascript
// server.js に追加
const isDevelopment = process.env.NODE_ENV === 'development' || process.platform === 'darwin';

if (isDevelopment) {
    console.log('🍎 macOS開発環境: 高品質シミュレーションモードを使用');
    // 現在の実装を継続使用
} else {
    console.log('🐧 Ubuntu本番環境: 実際のZoom音声キャプチャを使用');
    // PulseAudio統合を使用
}
```

## 推奨する開発フロー

### 開発段階（macOS）
1. **現在のシミュレーション音声を使用**
   - 高品質なシミュレーション音声で機能テスト
   - API動作、ファイル処理、Django統合のテスト

### テスト段階（macOS）
2. **BlackHole + 手動音声ファイル**
   - 実際の会議音声をBlackHoleで録音
   - 録音ファイルをシステムに手動で投入してテスト

### 本番段階（Ubuntu）
3. **PulseAudio統合**
   - 実際のZoom会議音声を自動キャプチャ
   - システム音声の直接録音

## 即座に実装できる解決策

現在の開発を継続するために、macOS用の設定を追加しましょう：