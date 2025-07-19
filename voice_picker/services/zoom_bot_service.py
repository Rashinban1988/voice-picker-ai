import requests
import json
import os
import re
import uuid
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from ..models import UploadedFile
from ..models.uploaded_file import Status
from ..tasks import transcribe_and_save_async, generate_hls_async
import logging

logger = logging.getLogger(__name__)

class ZoomBotService:
    def __init__(self):
        self.bot_server_url = getattr(settings, 'ZOOM_BOT_SERVER_URL', 'http://localhost:4000')
        self.recordings_path = getattr(settings, 'ZOOM_RECORDINGS_PATH', 
                                     os.path.join(settings.MEDIA_ROOT, 'zoom_recordings'))
        self.ensure_recordings_directory()
    
    def ensure_recordings_directory(self):
        """録画保存ディレクトリの作成"""
        if not os.path.exists(self.recordings_path):
            os.makedirs(self.recordings_path, exist_ok=True)
    
    def parse_meeting_url(self, meeting_url):
        """ZoomのURLから会議情報を抽出"""
        patterns = [
            r'zoom\.us/j/(\d+)(?:\?pwd=(.+))?',
            r'zoom\.us/meeting/(\d+)(?:\?pwd=(.+))?',
            r'(\d+)\.zoom\.us/j/(\d+)(?:\?pwd=(.+))?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, meeting_url)
            if match:
                if len(match.groups()) == 2:
                    return {
                        'meeting_number': match.group(1),
                        'password': match.group(2)
                    }
                else:
                    return {
                        'meeting_number': match.group(2),
                        'password': match.group(3)
                    }
        
        # 数字のみの場合（会議番号直接入力）
        if re.match(r'^\d+$', meeting_url):
            return {
                'meeting_number': meeting_url,
                'password': None
            }
        
        raise ValueError("Invalid Zoom meeting URL or meeting number")
    
    def start_meeting_recording(self, meeting_url, organization_id, user_name=None):
        """会議録画を開始"""
        try:
            # 会議情報を解析
            meeting_info = self.parse_meeting_url(meeting_url)
            
            # UploadedFileレコードを事前作成
            uploaded_file = UploadedFile.objects.create(
                organization_id=organization_id,
                file='',  # 後で更新
                status=Status.PROCESSING,
                source_type='zoom_meeting',
                meeting_url=meeting_url,
                meeting_number=meeting_info['meeting_number'],
                recording_start_time=timezone.now()
            )
            
            logger.info(f"Created UploadedFile record: {uploaded_file.id}")
            
            # Zoom Bot Server API呼び出し
            response = requests.post(
                f"{self.bot_server_url}/api/zoom/start-recording",
                json={
                    'meetingUrl': meeting_url,
                    'userName': user_name or 'Voice Picker AI Bot',
                    'uploadedFileId': str(uploaded_file.id)
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Bot server error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if not result.get('success'):
                raise Exception(f"Recording start failed: {result.get('error', 'Unknown error')}")
            
            # セッションID保存
            uploaded_file.zoom_session_id = result.get('sessionId')
            uploaded_file.save()
            
            logger.info(f"Recording started successfully: {uploaded_file.id}")
            
            return {
                'success': True,
                'uploaded_file_id': str(uploaded_file.id),
                'session_id': result.get('sessionId'),
                'meeting_number': meeting_info['meeting_number']
            }
            
        except Exception as e:
            logger.error(f"Recording start error: {e}")
            
            # エラー時はステータスを更新
            try:
                uploaded_file.status = Status.ERROR
                uploaded_file.save()
            except:
                pass
            
            raise
    
    def stop_meeting_recording(self, uploaded_file_id):
        """会議録画を停止"""
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            
            if not uploaded_file.zoom_session_id:
                raise Exception("No active recording session found")
            
            # Zoom Bot Server API呼び出し
            response = requests.post(
                f"{self.bot_server_url}/api/zoom/stop-recording",
                json={
                    'sessionId': uploaded_file.zoom_session_id
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Bot server error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if not result.get('success'):
                raise Exception(f"Recording stop failed: {result.get('error', 'Unknown error')}")
            
            # 録画終了時刻更新
            uploaded_file.recording_end_time = timezone.now()
            
            # 録画ファイルの確認と設定
            audio_file_path = result.get('audioFile')
            if audio_file_path and os.path.exists(audio_file_path):
                # メディアディレクトリからの相対パスを計算
                relative_path = os.path.relpath(audio_file_path, settings.MEDIA_ROOT)
                uploaded_file.file = relative_path
                uploaded_file.status = Status.COMPLETED
                
                # 音声ファイルの長さを取得
                self.set_audio_duration(uploaded_file, audio_file_path)
            else:
                uploaded_file.status = Status.ERROR
                logger.error(f"Audio file not found: {audio_file_path}")
            
            uploaded_file.save()
            
            # 録画が成功した場合、非同期で転写処理を開始
            if uploaded_file.status == Status.COMPLETED:
                logger.info(f"Starting transcription for: {uploaded_file.id}")
                
                # 転写処理開始
                transcribe_and_save_async.delay(
                    uploaded_file.file.path,
                    str(uploaded_file.id)
                )
                
                # HLS生成開始（常に実行）
                logger.info(f"Starting HLS generation for: {uploaded_file.id}")
                generate_hls_async.delay(str(uploaded_file.id))
            
            return {
                'success': True,
                'uploaded_file_id': str(uploaded_file.id),
                'status': uploaded_file.status
            }
            
        except UploadedFile.DoesNotExist:
            raise Exception("UploadedFile not found")
        except Exception as e:
            logger.error(f"Recording stop error: {e}")
            raise
    
    def get_recording_status(self, uploaded_file_id):
        """録画状態を取得"""
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            
            if not uploaded_file.zoom_session_id:
                return {
                    'status': 'not_found',
                    'message': 'No session found'
                }
            
            # Bot Serverから状態取得
            response = requests.get(
                f"{self.bot_server_url}/api/zoom/recording-status/{uploaded_file.zoom_session_id}",
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    'status': 'error',
                    'message': f"Bot server error: {response.status_code}"
                }
            
            bot_status = response.json()
            
            return {
                'status': bot_status.get('status', 'unknown'),
                'uploaded_file_id': str(uploaded_file.id),
                'meeting_number': uploaded_file.meeting_number,
                'recording_start_time': uploaded_file.recording_start_time,
                'recording_end_time': uploaded_file.recording_end_time,
                'file_status': uploaded_file.status
            }
            
        except UploadedFile.DoesNotExist:
            return {
                'status': 'not_found',
                'message': 'UploadedFile not found'
            }
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def set_audio_duration(self, uploaded_file, audio_file_path):
        """音声ファイルの長さを設定"""
        try:
            from moviepy.editor import AudioFileClip
            
            with AudioFileClip(audio_file_path) as audio:
                uploaded_file.duration = audio.duration
                
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
            uploaded_file.duration = 0.0
    
    def has_video_file(self, uploaded_file):
        """動画ファイルが存在するかチェック"""
        # 現在の実装では音声のみなのでFalse
        # 将来的に動画録画も対応する場合はここを変更
        return False
    
    def get_all_active_recordings(self):
        """全てのアクティブな録画を取得"""
        try:
            response = requests.get(
                f"{self.bot_server_url}/api/zoom/active-recordings",
                timeout=10
            )
            
            if response.status_code != 200:
                return []
            
            result = response.json()
            return result.get('recordings', [])
            
        except Exception as e:
            logger.error(f"Active recordings check error: {e}")
            return []
    
    def validate_meeting_url(self, meeting_url):
        """会議URLの妥当性を検証"""
        try:
            meeting_info = self.parse_meeting_url(meeting_url)
            
            # Bot Serverで解析テスト
            response = requests.post(
                f"{self.bot_server_url}/api/zoom/parse-url",
                json={'meetingUrl': meeting_url},
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    'valid': False,
                    'error': f"Server error: {response.status_code}"
                }
            
            result = response.json()
            
            return {
                'valid': result.get('success', False),
                'meeting_number': meeting_info['meeting_number'],
                'password_required': bool(meeting_info.get('password'))
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }