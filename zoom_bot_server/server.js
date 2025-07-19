const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const ZoomJWTGenerator = require('./src/auth/jwtGenerator');
const MeetingService = require('./src/services/meetingService');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 4000;

// ミドルウェア設定
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// サービス初期化
const jwtGenerator = new ZoomJWTGenerator(
    process.env.ZOOM_MEETING_SDK_KEY,
    process.env.ZOOM_MEETING_SDK_SECRET
);

const meetingService = new MeetingService();

// Environment detection for development vs production
const isDevelopmentEnvironment = process.env.PRODUCTION !== 'true';

console.log(`🖥️  Platform: ${process.platform}`);
console.log(`🔧 Environment: ${isDevelopmentEnvironment ? 'Development (macOS host)' : 'Production (Ubuntu)'}`);
console.log(`📦 Container: ${process.env.NODE_ENV || 'development'}`);

if (isDevelopmentEnvironment) {
    console.log('🍎 開発環境: 高品質シミュレーション音声を使用');
    console.log('📝 実際の音声テスト用: macOSホストでBlackHole + ffmpeg を使用可能');
    console.log('🔗 本番テスト用: Ubuntuホストに接続してPulseAudio統合テスト可能');
} else {
    console.log('🐧 本番環境: PulseAudio統合で実際の音声キャプチャ');
}

// エラーハンドラー
const asyncHandler = (fn) => (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
};

// JWT生成エンドポイント
app.post('/api/zoom/jwt', asyncHandler(async (req, res) => {
    const { meetingNumber, role } = req.body;
    
    if (!meetingNumber) {
        return res.status(400).json({
            error: 'Meeting number is required'
        });
    }

    const token = jwtGenerator.generateJWT(meetingNumber, role);
    
    res.json({
        success: true,
        token: token,
        sdkKey: process.env.ZOOM_MEETING_SDK_KEY,
        meetingNumber: meetingNumber,
        role: role || 0
    });
}));

// JWT検証エンドポイント
app.post('/api/zoom/validate', asyncHandler(async (req, res) => {
    const { token } = req.body;
    const result = jwtGenerator.validateJWT(token);
    
    res.json(result);
}));

// 会議録画開始エンドポイント
app.post('/api/zoom/start-recording', asyncHandler(async (req, res) => {
    const { meetingUrl, userName, uploadedFileId } = req.body;
    
    if (!meetingUrl) {
        return res.status(400).json({
            error: 'Meeting URL is required'
        });
    }

    // 会議情報を解析
    const meetingInfo = meetingService.parseMeetingUrl(meetingUrl);
    
    // JWT生成
    const token = jwtGenerator.generateJWT(meetingInfo.meetingNumber, 0);
    
    // セッションID生成
    const sessionId = uuidv4();
    
    // 録画開始
    const result = await meetingService.startRecording(sessionId, {
        meetingNumber: meetingInfo.meetingNumber,
        password: meetingInfo.password,
        userName: userName || 'Recording Bot',
        uploadedFileId,
        meetingUrl,
        jwt: token
    });
    
    res.json({
        ...result,
        sessionId,
        meetingNumber: meetingInfo.meetingNumber
    });
}));

// 会議録画停止エンドポイント
app.post('/api/zoom/stop-recording', asyncHandler(async (req, res) => {
    const { sessionId } = req.body;
    
    if (!sessionId) {
        return res.status(400).json({
            error: 'Session ID is required'
        });
    }

    const result = await meetingService.stopRecording(sessionId);
    
    res.json(result);
}));

// 録画状態確認エンドポイント
app.get('/api/zoom/recording-status/:sessionId', asyncHandler(async (req, res) => {
    const { sessionId } = req.params;
    
    const status = meetingService.getRecordingStatus(sessionId);
    
    res.json(status);
}));

// 全録画状態確認エンドポイント
app.get('/api/zoom/active-recordings', asyncHandler(async (req, res) => {
    const recordings = meetingService.getAllActiveRecordings();
    
    res.json({
        success: true,
        recordings: recordings,
        count: recordings.length
    });
}));

// 会議URL解析エンドポイント
app.post('/api/zoom/parse-url', asyncHandler(async (req, res) => {
    const { meetingUrl } = req.body;
    
    if (!meetingUrl) {
        return res.status(400).json({
            error: 'Meeting URL is required'
        });
    }

    try {
        const meetingInfo = meetingService.parseMeetingUrl(meetingUrl);
        res.json({
            success: true,
            ...meetingInfo
        });
    } catch (error) {
        res.status(400).json({
            error: error.message
        });
    }
}));

// ヘルスチェック
app.get('/health', (req, res) => {
    res.json({
        status: 'OK',
        timestamp: new Date().toISOString(),
        environment: process.env.NODE_ENV,
        activeRecordings: meetingService.getAllActiveRecordings().length
    });
});

// SDK診断エンドポイント
app.get('/api/zoom/sdk-status', (req, res) => {
    res.json({
        status: 'OK',
        sdk: {
            key: process.env.ZOOM_MEETING_SDK_KEY ? 
                `${process.env.ZOOM_MEETING_SDK_KEY.substring(0, 8)}...` : 'NOT_SET',
            secret: process.env.ZOOM_MEETING_SDK_SECRET ? 
                `${process.env.ZOOM_MEETING_SDK_SECRET.substring(0, 8)}...` : 'NOT_SET',
            keyLength: process.env.ZOOM_MEETING_SDK_KEY?.length || 0,
            secretLength: process.env.ZOOM_MEETING_SDK_SECRET?.length || 0
        },
        environment: {
            arch: process.arch,
            platform: process.platform,
            nodeVersion: process.version
        },
        paths: {
            recordingsPath: process.env.RECORDINGS_BASE_PATH,
            sdkPath: '/app/zoom_meeting_sdk/libmeetingsdk.so'
        },
        activeRecordings: meetingService.getAllActiveRecordings()
    });
});

// エラーハンドリングミドルウェア
app.use((error, req, res, next) => {
    console.error('Error:', error);
    res.status(500).json({
        error: 'Internal server error',
        message: error.message,
        ...(process.env.NODE_ENV === 'development' && { stack: error.stack })
    });
});

// 404ハンドラー
app.use((req, res) => {
    res.status(404).json({
        error: 'Not found',
        path: req.path
    });
});

// サーバー起動
app.listen(PORT, () => {
    console.log(`🚀 Zoom Meeting Bot Server running on port ${PORT}`);
    console.log(`Environment: ${process.env.NODE_ENV}`);
    console.log(`Recordings path: ${process.env.RECORDINGS_BASE_PATH}`);
});

// 優雅な停止処理
process.on('SIGTERM', () => {
    console.log('Received SIGTERM, shutting down gracefully...');
    // アクティブな録画を停止
    const activeRecordings = meetingService.getAllActiveRecordings();
    console.log(`Stopping ${activeRecordings.length} active recordings...`);
    
    process.exit(0);
});

module.exports = app;