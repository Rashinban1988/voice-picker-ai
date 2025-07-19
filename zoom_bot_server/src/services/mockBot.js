#!/usr/bin/env node

/**
 * Mock Bot for testing purposes
 * 実際のLinux SDKボットが完成するまでの仮実装
 */

const fs = require('fs');
const path = require('path');

class MockZoomBot {
    constructor(configPath) {
        this.config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        this.isRunning = false;
    }

    async start() {
        console.log('STARTING_BOT');
        console.log(`Meeting: ${this.config.meetingNumber}`);
        console.log(`Username: ${this.config.userName}`);
        
        // 認証シミュレーション
        await this.sleep(2000);
        console.log('AUTHENTICATION_SUCCESS');
        
        // 会議参加シミュレーション
        await this.sleep(3000);
        console.log('MEETING_JOINED');
        
        this.isRunning = true;
        
        // 録画開始シミュレーション
        await this.sleep(1000);
        console.log('RECORDING_STARTED');
        
        // 疑似音声データ生成
        this.generateMockAudio();
        
        // 終了シグナル待機
        process.on('SIGTERM', () => {
            this.stop();
        });
        
        process.on('SIGINT', () => {
            this.stop();
        });
        
        // 疑似的な録画継続
        this.recordingInterval = setInterval(() => {
            console.log('RECORDING_HEARTBEAT');
        }, 10000);
    }

    async stop() {
        console.log('STOPPING_RECORDING');
        this.isRunning = false;
        
        if (this.recordingInterval) {
            clearInterval(this.recordingInterval);
        }
        
        // 録画停止シミュレーション
        await this.sleep(1000);
        console.log('RECORDING_STOPPED');
        
        // 会議退出シミュレーション
        await this.sleep(500);
        console.log('MEETING_LEFT');
        
        process.exit(0);
    }

    generateMockAudio() {
        // 疑似音声ファイル生成（実際には何も生成しない）
        const audioPath = this.config.audioFile;
        const audioDir = path.dirname(audioPath);
        
        if (!fs.existsSync(audioDir)) {
            fs.mkdirSync(audioDir, { recursive: true });
        }
        
        // 空のWAVファイルを作成（テスト用）
        const mockAudioData = Buffer.alloc(1024, 0);
        fs.writeFileSync(audioPath, mockAudioData);
        
        console.log(`AUDIO_FILE_CREATED: ${audioPath}`);
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// メイン実行
const args = process.argv.slice(2);
const configIndex = args.indexOf('--config');

if (configIndex === -1 || !args[configIndex + 1]) {
    console.error('Usage: node mockBot.js --config <config.json>');
    process.exit(1);
}

const configPath = args[configIndex + 1];
const bot = new MockZoomBot(configPath);

bot.start().catch(error => {
    console.error('ERROR:', error.message);
    process.exit(1);
});