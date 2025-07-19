import requests
import json
import re
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class ZoomAPIService:
    """Zoom REST API統合サービス"""
    
    def __init__(self):
        self.base_url = "https://api.zoom.us/v2"
        self.jwt_token = getattr(settings, 'ZOOM_JWT_TOKEN', None)
        self.account_id = getattr(settings, 'ZOOM_ACCOUNT_ID', None)
        self.client_id = getattr(settings, 'ZOOM_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'ZOOM_CLIENT_SECRET', None)
        self._access_token = None
        self._token_expires_at = None
    
    def get_access_token(self):
        """OAuth2アクセストークンを取得"""
        if self._access_token and self._token_expires_at and datetime.now() < self._token_expires_at:
            return self._access_token
        
        # OAuth認証情報が未設定の場合はエラーをスキップ
        if not self.client_id or self.client_id == 'your_zoom_client_id_here':
            logger.warning("Zoom OAuth credentials not configured, skipping OAuth features")
            return None
        
        try:
            # Server-to-Server OAuth認証
            auth_url = "https://zoom.us/oauth/token"
            
            payload = {
                'grant_type': 'account_credentials',
                'account_id': self.account_id
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                auth_url,
                data=payload,
                headers=headers,
                auth=(self.client_id, self.client_secret)
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self._access_token = token_data['access_token']
                expires_in = token_data.get('expires_in', 3600)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                return self._access_token
            else:
                logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None
    
    def get_meeting_details(self, meeting_id):
        """会議の詳細情報を取得"""
        access_token = self.get_access_token()
        if not access_token:
            raise Exception("Failed to get access token")
        
        try:
            url = f"{self.base_url}/meetings/{meeting_id}"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                meeting_data = response.json()
                return self._format_meeting_details(meeting_data)
            else:
                logger.error(f"Failed to get meeting details: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting meeting details: {e}")
            return None
    
    def _format_meeting_details(self, meeting_data):
        """会議データをフォーマット"""
        try:
            # 時間をJSTに変換
            start_time_str = meeting_data.get('start_time')
            start_time = None
            if start_time_str:
                # ISO 8601形式をパース
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                # JSTに変換
                start_time = start_time.astimezone(timezone.get_current_timezone())
            
            return {
                'meeting_id': meeting_data.get('id'),
                'topic': meeting_data.get('topic', ''),
                'start_time': start_time,
                'duration': meeting_data.get('duration', 60),  # 分
                'timezone': meeting_data.get('timezone', 'Asia/Tokyo'),
                'password': meeting_data.get('password', ''),
                'join_url': meeting_data.get('join_url', ''),
                'host_email': meeting_data.get('host_email', ''),
                'status': meeting_data.get('status', 'waiting'),
                'type': meeting_data.get('type', 2),  # 2=scheduled meeting
                'created_at': meeting_data.get('created_at'),
                'agenda': meeting_data.get('agenda', ''),
                'settings': meeting_data.get('settings', {}),
                'can_record': self._can_record_meeting(meeting_data),
                'estimated_end_time': self._calculate_end_time(start_time, meeting_data.get('duration', 60))
            }
        except Exception as e:
            logger.error(f"Error formatting meeting details: {e}")
            return None
    
    def _can_record_meeting(self, meeting_data):
        """会議が録画可能かチェック"""
        settings = meeting_data.get('settings', {})
        
        # 録画設定をチェック
        auto_recording = settings.get('auto_recording', 'none')
        allow_multiple_devices = settings.get('allow_multiple_devices', False)
        
        return {
            'auto_recording': auto_recording,
            'cloud_recording': auto_recording in ['cloud', 'both'],
            'local_recording': auto_recording in ['local', 'both'],
            'allow_multiple_devices': allow_multiple_devices,
            'recording_authentication': settings.get('recording_authentication', False)
        }
    
    def _calculate_end_time(self, start_time, duration_minutes):
        """終了時刻を計算"""
        if start_time and duration_minutes:
            return start_time + timedelta(minutes=duration_minutes)
        return None
    
    def parse_meeting_url_advanced(self, meeting_url):
        """会議URLから詳細情報を取得"""
        try:
            # 基本的な会議IDを抽出
            meeting_id = self._extract_meeting_id(meeting_url)
            if not meeting_id:
                raise ValueError("Invalid meeting URL")
            
            # OAuth認証が利用可能な場合のみAPI呼び出し
            access_token = self.get_access_token()
            if access_token:
                # Zoom APIから詳細情報を取得
                meeting_details = self.get_meeting_details(meeting_id)
                if meeting_details:
                    return meeting_details
            
            # APIから取得できない場合またはOAuth未設定の場合はベーシック情報を返す
            logger.info(f"Using fallback meeting details for {meeting_id}")
            return {
                'meeting_id': meeting_id,
                'topic': f'会議 {meeting_id}',
                'start_time': None,
                    'duration': 60,
                    'password': self._extract_password(meeting_url),
                    'join_url': meeting_url,
                    'can_record': {'auto_recording': 'none', 'cloud_recording': False, 'local_recording': False},
                    'is_scheduled': False,
                    'api_available': False
                }
            
            meeting_details['is_scheduled'] = meeting_details.get('type') == 2
            meeting_details['api_available'] = True
            return meeting_details
            
        except Exception as e:
            logger.error(f"Error parsing meeting URL: {e}")
            raise
    
    def _extract_meeting_id(self, meeting_url):
        """URLから会議IDを抽出"""
        patterns = [
            r'zoom\.us/j/(\d+)',
            r'zoom\.us/meeting/(\d+)',
            r'(\d+)\.zoom\.us/j/(\d+)',
            r'^(\d+)$'  # 会議番号のみ
        ]
        
        for pattern in patterns:
            match = re.search(pattern, meeting_url)
            if match:
                return match.group(1) if pattern != r'(\d+)\.zoom\.us/j/(\d+)' else match.group(2)
        
        return None
    
    def _extract_password(self, meeting_url):
        """URLからパスワードを抽出"""
        password_match = re.search(r'[?&]pwd=([^&]+)', meeting_url)
        return password_match.group(1) if password_match else None
    
    def validate_meeting_for_recording(self, meeting_id):
        """録画可能性を検証"""
        try:
            meeting_details = self.get_meeting_details(meeting_id)
            if not meeting_details:
                return {
                    'valid': False,
                    'error': 'Meeting not found or access denied'
                }
            
            # 現在時刻との比較
            now = timezone.now()
            start_time = meeting_details.get('start_time')
            
            if start_time and start_time < now:
                # 過去の会議
                end_time = meeting_details.get('estimated_end_time')
                if end_time and end_time < now:
                    return {
                        'valid': False,
                        'error': 'Meeting has already ended'
                    }
            
            return {
                'valid': True,
                'meeting_details': meeting_details,
                'can_schedule': bool(start_time and start_time > now),
                'can_record_now': meeting_details.get('status') == 'started'
            }
            
        except Exception as e:
            logger.error(f"Error validating meeting: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def get_user_meetings(self, user_id='me', type_filter='scheduled'):
        """ユーザーの会議一覧を取得"""
        access_token = self.get_access_token()
        if not access_token:
            raise Exception("Failed to get access token")
        
        try:
            url = f"{self.base_url}/users/{user_id}/meetings"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'type': type_filter,
                'page_size': 100
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user meetings: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user meetings: {e}")
            return None