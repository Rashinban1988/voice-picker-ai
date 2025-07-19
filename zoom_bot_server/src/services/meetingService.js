const axios = require('axios');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const JWTGenerator = require('../utils/jwtGenerator');

class MeetingService {
    constructor() {
        this.activeBots = new Map(); // sessionId -> botProcess
        this.recordingsPath = process.env.RECORDINGS_BASE_PATH || '/tmp/recordings';
        this.jwtGenerator = new JWTGenerator();
        this.ensureRecordingsDirectory();
    }

    ensureRecordingsDirectory() {
        if (!fs.existsSync(this.recordingsPath)) {
            fs.mkdirSync(this.recordingsPath, { recursive: true });
        }
    }

    parseMeetingUrl(meetingUrl) {
        const patterns = [
            /zoom\.us\/j\/(\d+)(?:\?pwd=(.+))?/,
            /zoom\.us\/meeting\/(\d+)(?:\?pwd=(.+))?/,
            /(\d+)\.zoom\.us\/j\/(\d+)(?:\?pwd=(.+))?/,
        ];
        
        for (const pattern of patterns) {
            const match = meetingUrl.match(pattern);
            if (match) {
                return {
                    meetingNumber: match[1] || match[2],
                    password: match[2] || match[3] || null
                };
            }
        }
        
        // 数字のみの場合（会議番号直接入力）
        if (/^\d+$/.test(meetingUrl)) {
            return {
                meetingNumber: meetingUrl,
                password: null
            };
        }
        
        throw new Error('Invalid Zoom meeting URL or meeting number');
    }

    async notifyDjango(endpoint, data) {
        try {
            const response = await axios.post(
                `${process.env.DJANGO_API_URL}${endpoint}`,
                data,
                {
                    headers: {
                        'Authorization': `Bearer ${process.env.DJANGO_API_TOKEN}`,
                        'Content-Type': 'application/json'
                    }
                }
            );
            return response.data;
        } catch (error) {
            console.error('Django notification error:', error.message);
            throw error;
        }
    }

    async startRecording(sessionId, meetingConfig) {
        const { meetingNumber, password, userName, uploadedFileId, meetingUrl } = meetingConfig;
        
        // uploadedFileIdの検証と処理
        let actualUploadedFileId = uploadedFileId;
        if (uploadedFileId && this.isValidUUID(uploadedFileId)) {
            console.log(`Using provided UploadedFile ID: ${uploadedFileId}`);
            actualUploadedFileId = uploadedFileId;
        } else {
            // 有効なUUIDでない場合は、Django APIを呼び出してUploadedFileレコードを作成
            try {
                const uploadedFile = await this.createUploadedFileRecord(meetingUrl, meetingNumber, sessionId);
                actualUploadedFileId = uploadedFile.id;
                console.log(`Created new UploadedFile record: ${actualUploadedFileId}`);
            } catch (error) {
                console.error('Failed to create UploadedFile record:', error);
                throw error;
            }
        }
        
        // 録画用ディレクトリ作成
        const sessionPath = path.join(this.recordingsPath, sessionId);
        if (!fs.existsSync(sessionPath)) {
            fs.mkdirSync(sessionPath, { recursive: true });
        }

        // SDK認証設定を生成
        let authConfig = {};
        try {
            authConfig = this.jwtGenerator.generateBotAuthConfig(
                meetingNumber, 
                password || '', 
                userName || 'Recording Bot'
            );
            console.log('Generated auth config for meeting:', meetingNumber);
        } catch (error) {
            console.warn('Failed to generate SDK auth config:', error.message);
            console.log('Proceeding with simulation mode');
        }

        // 設定ファイル作成
        const configPath = path.join(sessionPath, 'config.json');
        const botConfig = {
            meetingNumber,
            password: password || '',
            userName: userName || 'Recording Bot',
            outputPath: sessionPath,
            audioFile: path.join(sessionPath, 'audio.wav'),
            videoFile: path.join(sessionPath, 'video.mp4'),
            sessionId,
            uploadedFileId: actualUploadedFileId,
            // SDK認証情報
            auth: authConfig
        };

        fs.writeFileSync(configPath, JSON.stringify(botConfig, null, 2));

        // C++ Zoom Meeting SDKボットを使用
        const botExecutablePath = path.join(__dirname, '../../zoom_meeting_sdk/bot_implementation/build/zoom_meeting_bot');
        
        const botProcess = spawn(botExecutablePath, [
            '--config', configPath
        ], {
            stdio: ['pipe', 'pipe', 'pipe'],
            detached: false,
            env: {
                ...process.env,
                ZOOM_MEETING_SDK_KEY: process.env.ZOOM_MEETING_SDK_KEY,
                ZOOM_MEETING_SDK_SECRET: process.env.ZOOM_MEETING_SDK_SECRET,
                LD_LIBRARY_PATH: '/app/zoom_meeting_sdk:/app/zoom_meeting_sdk/qt_libs/Qt/lib:/app/zoom_meeting_sdk/bot_implementation/build:/lib:/usr/lib:/usr/lib/x86_64-linux-gnu:' + (process.env.LD_LIBRARY_PATH || ''),
                PATH: '/app/zoom_meeting_sdk:/app/zoom_meeting_sdk/bot_implementation/build:' + (process.env.PATH || ''),
                QT_PLUGIN_PATH: '/app/zoom_meeting_sdk/qt_libs/Qt/plugins',
                QT_QPA_PLATFORM: 'offscreen',
                DISPLAY: ':99'
            }
        });

        // プロセス管理
        this.activeBots.set(sessionId, {
            process: botProcess,
            config: botConfig,
            startTime: new Date(),
            status: 'starting'
        });

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                botProcess.kill();
                this.activeBots.delete(sessionId);
                reject(new Error('Bot startup timeout'));
            }, 60000); // 60秒タイムアウト（SDK初期化時間を考慮）

            botProcess.stdout.on('data', (data) => {
                const message = data.toString();
                console.log(`Bot ${sessionId} output:`, message);
                
                // より柔軟なメッセージ検出
                if (message.includes('MEETING_JOINED') || 
                    message.includes('MEETING_JOINED_SUCCESSFULLY') || 
                    message.includes('FALLBACK_TO_SIMULATION_MODE') ||
                    message.includes('RECORDING_STARTED')) {
                    clearTimeout(timeout);
                    this.activeBots.get(sessionId).status = 'recording';
                    
                    let statusMessage = 'Recording started';
                    if (message.includes('MEETING_JOINED_SUCCESSFULLY')) {
                        statusMessage = 'Successfully joined real Zoom meeting and started recording';
                    } else if (message.includes('FALLBACK_TO_SIMULATION_MODE')) {
                        statusMessage = 'Could not join meeting, using simulation mode';
                    } else if (message.includes('MEETING_JOINED')) {
                        statusMessage = 'Joined meeting in simulation mode';
                    }
                    
                    resolve({
                        success: true,
                        sessionId,
                        message: statusMessage
                    });
                }
            });

            botProcess.stderr.on('data', (data) => {
                const error = data.toString();
                console.error(`Bot ${sessionId} error:`, error);
                
                if (error.includes('AUTHENTICATION_FAILED')) {
                    clearTimeout(timeout);
                    this.activeBots.delete(sessionId);
                    reject(new Error('Authentication failed'));
                }
            });

            botProcess.on('exit', async (code) => {
                clearTimeout(timeout);
                console.log(`Bot ${sessionId} exited with code ${code}`);
                
                // 録画完了後の処理
                if (code === 0 && this.activeBots.has(sessionId)) {
                    const botInfo = this.activeBots.get(sessionId);
                    this.activeBots.delete(sessionId);
                    
                    // 録画ファイルの確認
                    const audioPath = botInfo.config.audioFile;
                    if (fs.existsSync(audioPath)) {
                        try {
                            // Djangoに録画完了を通知
                            if (botInfo.config.uploadedFileId) {
                                const notificationData = {
                                    sessionId: sessionId,
                                    uploadedFileId: botInfo.config.uploadedFileId,
                                    audioFile: audioPath,
                                    meetingNumber: botInfo.config.meetingNumber,
                                    duration: Math.floor((Date.now() - botInfo.startTime) / 1000)
                                };
                                console.log(`Notifying Django of recording completion:`, notificationData);
                                
                                const djangoResponse = await this.notifyDjango('/voice_picker/api/zoom/recording-completed/', notificationData);
                                console.log('Django notification sent successfully:', djangoResponse);
                            } else {
                                console.warn('No uploadedFileId found in botInfo.config');
                            }
                        } catch (error) {
                            console.error('Failed to notify Django:', error.message);
                            console.error('Full error:', error);
                        }
                    }
                } else if (code !== 0 && this.activeBots.has(sessionId)) {
                    this.activeBots.delete(sessionId);
                    reject(new Error(`Bot exited with code ${code}`));
                }
            });
        });
    }

    async stopRecording(sessionId) {
        const botInfo = this.activeBots.get(sessionId);
        if (!botInfo) {
            throw new Error('No active recording found for this session');
        }

        return new Promise(async (resolve, reject) => {
            const timeout = setTimeout(() => {
                botInfo.process.kill('SIGKILL');
                this.activeBots.delete(sessionId);
                reject(new Error('Bot stop timeout'));
            }, 10000); // 10秒タイムアウト

            botInfo.process.on('exit', async (code) => {
                clearTimeout(timeout);
                this.activeBots.delete(sessionId);
                
                // 録画ファイルの確認
                const audioPath = botInfo.config.audioFile;
                if (fs.existsSync(audioPath)) {
                    try {
                        // Djangoに録画完了を通知
                        if (botInfo.config.uploadedFileId) {
                            await this.notifyDjango('/voice_picker/api/zoom/recording-completed/', {
                                sessionId: sessionId,
                                uploadedFileId: botInfo.config.uploadedFileId,
                                audioFile: audioPath,
                                meetingNumber: botInfo.config.meetingNumber,
                                duration: Math.floor((Date.now() - botInfo.startTime) / 1000)
                            });
                        }
                    } catch (error) {
                        console.error('Failed to notify Django:', error);
                    }
                    
                    resolve({
                        success: true,
                        sessionId,
                        audioFile: audioPath,
                        message: 'Recording stopped successfully'
                    });
                } else {
                    reject(new Error('Recording file not found'));
                }
            });

            // 優雅な停止を試行
            botInfo.process.kill('SIGTERM');
        });
    }

    getRecordingStatus(sessionId) {
        const botInfo = this.activeBots.get(sessionId);
        if (!botInfo) {
            return { status: 'not_found' };
        }

        return {
            status: botInfo.status,
            startTime: botInfo.startTime,
            sessionId: sessionId,
            config: botInfo.config
        };
    }

    getAllActiveRecordings() {
        const recordings = [];
        for (const [sessionId, botInfo] of this.activeBots) {
            recordings.push({
                sessionId,
                status: botInfo.status,
                startTime: botInfo.startTime,
                meetingNumber: botInfo.config.meetingNumber
            });
        }
        return recordings;
    }
    
    // UUID バリデーション
    isValidUUID(str) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        return uuidRegex.test(str);
    }
    
    // Django APIを呼び出してUploadedFileレコードを作成
    async createUploadedFileRecord(meetingUrl, meetingNumber, sessionId) {
        const response = await axios.post(
            `${process.env.DJANGO_API_URL}/voice_picker/api/zoom/create-uploaded-file/`,
            {
                meetingUrl: meetingUrl,
                meetingNumber: meetingNumber,
                sessionId: sessionId
            },
            {
                headers: {
                    'Authorization': `Bearer ${process.env.DJANGO_API_TOKEN}`,
                    'Content-Type': 'application/json'
                }
            }
        );
        
        if (response.status !== 200) {
            throw new Error(`Django API error: ${response.status} - ${response.data}`);
        }
        
        return response.data;
    }
}

module.exports = MeetingService;