const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');
const { createWriteStream } = require('fs');
const { pipeline } = require('stream').promises;

class ZoomRecordingDownloader {
    constructor(clientId, clientSecret, accountId) {
        this.clientId = clientId || process.env.ZOOM_CLIENT_ID;
        this.clientSecret = clientSecret || process.env.ZOOM_CLIENT_SECRET;
        this.accountId = accountId || process.env.ZOOM_ACCOUNT_ID;
        this.accessToken = null;
        this.tokenExpiry = null;
    }

    // Get OAuth access token
    async getAccessToken() {
        if (this.accessToken && this.tokenExpiry && new Date() < this.tokenExpiry) {
            return this.accessToken;
        }

        try {
            const response = await axios.post(
                'https://zoom.us/oauth/token',
                null,
                {
                    params: {
                        grant_type: 'account_credentials',
                        account_id: this.accountId
                    },
                    auth: {
                        username: this.clientId,
                        password: this.clientSecret
                    }
                }
            );

            this.accessToken = response.data.access_token;
            this.tokenExpiry = new Date(Date.now() + (response.data.expires_in - 60) * 1000);
            
            console.log('ZOOM_AUTH: Access token obtained');
            return this.accessToken;
        } catch (error) {
            console.error('ZOOM_AUTH_ERROR:', error.response?.data || error.message);
            throw error;
        }
    }

    // Get recording list for a meeting
    async getRecordings(meetingId) {
        const token = await this.getAccessToken();
        
        try {
            const response = await axios.get(
                `https://api.zoom.us/v2/meetings/${meetingId}/recordings`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            console.log('ZOOM_RECORDINGS: Found recordings for meeting', meetingId);
            return response.data;
        } catch (error) {
            if (error.response?.status === 404) {
                console.log('ZOOM_RECORDINGS: No recordings found for meeting', meetingId);
                return null;
            }
            throw error;
        }
    }

    // Download recording file
    async downloadRecording(downloadUrl, outputPath) {
        const token = await this.getAccessToken();
        
        try {
            console.log('ZOOM_DOWNLOAD: Downloading recording...');
            
            const response = await axios({
                method: 'GET',
                url: downloadUrl,
                responseType: 'stream',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            const writer = createWriteStream(outputPath);
            await pipeline(response.data, writer);
            
            console.log('ZOOM_DOWNLOAD: Recording saved to', outputPath);
            return outputPath;
        } catch (error) {
            console.error('ZOOM_DOWNLOAD_ERROR:', error.message);
            throw error;
        }
    }

    // Download all recordings for a meeting
    async downloadMeetingRecordings(meetingId, outputDir) {
        const recordings = await this.getRecordings(meetingId);
        
        if (!recordings || !recordings.recording_files) {
            console.log('ZOOM_RECORDINGS: No recording files available');
            return [];
        }

        await fs.mkdir(outputDir, { recursive: true });
        const downloadedFiles = [];

        for (const file of recordings.recording_files) {
            const fileName = `${file.recording_type}_${file.recording_start}.${file.file_extension}`;
            const outputPath = path.join(outputDir, fileName);
            
            console.log(`ZOOM_DOWNLOAD: Downloading ${file.recording_type} (${file.file_size} bytes)`);
            
            try {
                await this.downloadRecording(file.download_url, outputPath);
                downloadedFiles.push({
                    type: file.recording_type,
                    path: outputPath,
                    size: file.file_size,
                    duration: file.duration
                });
            } catch (error) {
                console.error(`ZOOM_DOWNLOAD_ERROR: Failed to download ${file.recording_type}:`, error.message);
            }
        }

        return downloadedFiles;
    }

    // Check if meeting has cloud recording enabled
    async checkCloudRecording(meetingId) {
        const token = await this.getAccessToken();
        
        try {
            const response = await axios.get(
                `https://api.zoom.us/v2/meetings/${meetingId}`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            const settings = response.data.settings;
            return {
                autoRecording: settings?.auto_recording || 'none',
                cloudRecording: settings?.cloud_recording || false,
                recordingAuthentication: settings?.recording_authentication || false
            };
        } catch (error) {
            console.error('ZOOM_API_ERROR:', error.response?.data || error.message);
            return null;
        }
    }
}

module.exports = ZoomRecordingDownloader;