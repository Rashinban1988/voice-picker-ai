# Zoom Web SDK実装による実際の会議音声録音

## 現在の問題

現在の実装では、以下の理由で実際の会議音声が録音されていません：

1. **Zoom Meeting SDKライブラリが存在しない**: `libmeetingsdk.so`が実際には存在しない
2. **SDK関数が見つからない**: `SDK_Init`、`SDK_JoinMeeting`などの関数が定義されていない
3. **フォールバック実装が使用される**: シミュレーション音声が生成される

## 解決策：Zoom Web SDKの使用

### 1. Zoom Web SDKとは
- ブラウザベースのJavaScript SDK
- 実際のZoom会議に参加可能
- 音声/映像のキャプチャが可能
- Meeting SDKより導入が簡単

### 2. 実装アプローチ

#### A. Node.jsでPuppeteerを使用
```javascript
// zoom_web_sdk_bot.js
const puppeteer = require('puppeteer');

class ZoomWebSDKBot {
    async joinMeeting(meetingUrl, userName) {
        const browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        
        const page = await browser.newPage();
        
        // 音声録音の設定
        await page.goto('chrome://flags/#disable-web-security');
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
        
        // Zoom Web SDKページを開く
        await page.goto(meetingUrl);
        
        // 会議に参加
        await page.click('#join-audio-button');
        
        // 音声録音開始
        await this.startAudioRecording(page);
    }
    
    async startAudioRecording(page) {
        // Web Audio APIを使用した音声録音
        await page.evaluate(() => {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    const recorder = new MediaRecorder(stream);
                    recorder.start();
                    
                    const chunks = [];
                    recorder.addEventListener('dataavailable', event => {
                        chunks.push(event.data);
                    });
                    
                    recorder.addEventListener('stop', () => {
                        const blob = new Blob(chunks, { type: 'audio/wav' });
                        // 音声データをNode.jsに送信
                        window.audioData = blob;
                    });
                });
        });
    }
}
```

#### B. Python + Seleniumを使用
```python
# zoom_web_sdk_bot.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

class ZoomWebSDKBot:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument("--use-fake-device-for-media-stream")
        
        self.driver = webdriver.Chrome(options=chrome_options)
    
    def join_meeting(self, meeting_url, username):
        self.driver.get(meeting_url)
        
        # 会議に参加
        join_button = self.driver.find_element_by_id("join-audio-button")
        join_button.click()
        
        # 音声録音開始
        self.start_audio_recording()
    
    def start_audio_recording(self):
        # Web Audio APIを使用した音声録音
        script = """
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                const recorder = new MediaRecorder(stream);
                recorder.start();
                
                const chunks = [];
                recorder.addEventListener('dataavailable', event => {
                    chunks.push(event.data);
                });
                
                window.audioRecorder = recorder;
                window.audioChunks = chunks;
            });
        """
        self.driver.execute_script(script)
```

### 3. 実装手順

#### ステップ1: Zoom Web SDKの設定
```bash
# Zoom Web SDKのインストール
npm install @zoomus/websdk
```

#### ステップ2: 認証設定
```javascript
// Zoom Web SDK認証
const ZoomSDK = require('@zoomus/websdk');

const client = ZoomSDK.ZoomMtg.init({
    leaveUrl: 'http://localhost:4000',
    success: function(res) {
        console.log('SDK initialized successfully');
    },
    error: function(res) {
        console.log('SDK initialization failed');
    }
});
```

#### ステップ3: 会議参加と録音
```javascript
// 会議に参加
client.join({
    meetingNumber: '12345678901',
    passWord: 'password',
    userName: 'RecordingBot',
    userEmail: 'bot@example.com',
    success: function(res) {
        console.log('Joined meeting successfully');
        startAudioRecording();
    },
    error: function(res) {
        console.log('Failed to join meeting');
    }
});

function startAudioRecording() {
    // 音声録音の実装
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            const recorder = new MediaRecorder(stream);
            recorder.start();
            
            const chunks = [];
            recorder.addEventListener('dataavailable', event => {
                chunks.push(event.data);
            });
            
            recorder.addEventListener('stop', () => {
                const blob = new Blob(chunks, { type: 'audio/wav' });
                saveAudioFile(blob);
            });
        });
}
```

## 次のステップ

現在のC++実装を完全に置き換えるか、Zoom Web SDKを使用した新しい実装を作成するかを決定する必要があります。

### 推奨アプローチ
1. **Zoom Web SDKの導入**: 実際の会議音声を録音可能
2. **Node.js + Puppeteerの使用**: 既存のアーキテクチャとの統合が容易
3. **段階的な移行**: 現在の実装を保持しながら新機能を追加

これにより、実際のZoom会議音声を録音できるようになります。