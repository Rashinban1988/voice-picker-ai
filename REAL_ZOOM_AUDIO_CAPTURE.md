# 実際のZoom会議音声キャプチャの実装

## 現在の状況

✅ **Zoom Meeting SDK統合**: 完全に動作  
✅ **会議認証**: JWTトークン生成が機能  
✅ **音声キャプチャ基盤**: PulseAudio統合完了  
⚠️ **実際の会議接続**: SDK関数検出済みだが、C++オブジェクト管理が必要

## 実際の音声キャプチャの方法

### 方法1: ホストマシンのPulseAudioを使用（推奨）

Ubuntu環境で実際のZoom会議音声をキャプチャする手順：

#### 1. ホストマシンでPulseAudio設定

```bash
# 1. 自動設定スクリプトを実行
bash /path/to/zoom_bot_server/scripts/setup_host_pulseaudio.sh

# または手動で設定：
# 仮想シンクを作成
pactl load-module module-null-sink sink_name=zoom_recorder sink_properties=device.description="Zoom_Recorder"

# TCP接続を有効化（コンテナからのアクセス用）
pactl load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12
```

#### 2. Zoomアプリの音声設定を変更

1. Zoomデスクトップアプリを開く
2. 設定 → オーディオ
3. スピーカー → "Zoom_Recorder" を選択
4. マイク設定はそのまま

#### 3. Docker設定を更新

`docker-compose.yaml` に以下を追加：

```yaml
services:
  zoom_bot_server:
    environment:
      - PULSE_SERVER=tcp:host.docker.internal:4713
    extra_hosts:
      - 'host.docker.internal:host-gateway'
```

#### 4. 録画を開始

```bash
curl -X POST http://localhost:4000/api/zoom/start-recording \
  -H "Content-Type: application/json" \
  -d '{
    "meetingUrl": "YOUR_ZOOM_MEETING_URL", 
    "userName": "録画ボット",
    "duration": 300
  }'
```

### 方法2: 完全なSDK統合（上級者向け）

Zoom Meeting SDKの完全なC++統合を実装する場合：

1. **C++クラス実装**
   - IAuthServiceEvent インターフェースの実装
   - IMeetingServiceEvent インターフェースの実装
   - IAudioRawDataHelper インターフェースの実装

2. **認証フロー**
   ```cpp
   // 認証
   IAuthService* auth_service = CreateAuthService();
   auth_service->SDKAuth(auth_context);
   
   // 会議参加
   IMeetingService* meeting_service = CreateMeetingService();
   meeting_service->Join(meeting_param);
   
   // 音声データ取得
   IAudioRawDataHelper* audio_helper = GetAudioRawdataHelper();
   audio_helper->subscribe(audio_receiver);
   ```

## 現在実装済みの機能

### ✅ 完了している機能

1. **SDK検出と読み込み**
   - libmeetingsdk.so の動的読み込み ✓
   - 必要な依存関係の解決 ✓
   - SDK関数の検出 ✓

2. **認証システム**
   - JWT生成 ✓
   - API Key/Secret 管理 ✓
   - トークン検証 ✓

3. **音声処理基盤**
   - WAV形式での録音 ✓
   - リアルタイム音声ストリーミング ✓
   - PulseAudio統合 ✓

4. **フォールバック機能**
   - 高品質シミュレーション音声 ✓
   - 自動フォールバック ✓

### 🔧 追加実装が必要な機能

1. **完全なSDK統合**
   - C++インターフェース実装
   - イベントハンドラー
   - エラー処理の強化

2. **音声キャプチャ最適化**
   - ノイズキャンセリング
   - 音量正規化
   - 複数話者の識別

## 推奨アプローチ

**現在の用途では方法1（PulseAudio）が最適です：**

1. **実装が簡単**: 既存のシステムを活用
2. **確実に動作**: OS レベルの音声キャプチャ
3. **設定が容易**: Zoomアプリの設定変更のみ
4. **品質が高い**: 圧縮前の音声を取得

実際にZoom会議の音声をキャプチャしたい場合は、方法1を使用してください。