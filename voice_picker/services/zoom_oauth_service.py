import requests
import base64
import json
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class ZoomOAuthService:
    """Zoom OAuth認証サービス"""
    
    def __init__(self):
        self.client_id = getattr(settings, 'ZOOM_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'ZOOM_CLIENT_SECRET', None)
        self.redirect_uri = getattr(settings, 'ZOOM_REDIRECT_URI', 'http://localhost:4000/auth/callback')
        self.base_url = 'https://zoom.us'
        
    def get_authorization_url(self, state=None):
        """OAuth認証URLを生成"""
        if not self.client_id:
            raise ValueError("ZOOM_CLIENT_ID が設定されていません")
            
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'meeting:write meeting:read recording:write recording:read user:read'
        }
        
        if state:
            params['state'] = state
            
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f'{self.base_url}/oauth/authorize?{query_string}'
    
    def exchange_code_for_token(self, authorization_code):
        """認証コードをアクセストークンに交換"""
        if not self.client_id or not self.client_secret:
            raise ValueError("Zoom OAuth認証情報が設定されていません")
            
        # Basic認証ヘッダーを作成
        credentials = f'{self.client_id}:{self.client_secret}'
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/oauth/token',
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # トークンをキャッシュに保存（1時間）
                cache.set(
                    f'zoom_access_token_{self.client_id}',
                    token_data['access_token'],
                    timeout=3600
                )
                
                if 'refresh_token' in token_data:
                    cache.set(
                        f'zoom_refresh_token_{self.client_id}',
                        token_data['refresh_token'],
                        timeout=30 * 24 * 3600  # 30日
                    )
                
                logger.info("Zoom OAuth認証成功")
                return token_data
            else:
                logger.error(f"Zoom OAuth token exchange failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Zoom OAuth token exchange error: {e}")
            return None
    
    def get_access_token(self):
        """キャッシュからアクセストークンを取得"""
        return cache.get(f'zoom_access_token_{self.client_id}')
    
    def refresh_access_token(self):
        """リフレッシュトークンを使用してアクセストークンを更新"""
        refresh_token = cache.get(f'zoom_refresh_token_{self.client_id}')
        
        if not refresh_token:
            logger.warning("Zoom refresh token not found")
            return None
            
        credentials = f'{self.client_id}:{self.client_secret}'
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/oauth/token',
                headers=headers,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # 新しいトークンをキャッシュに保存
                cache.set(
                    f'zoom_access_token_{self.client_id}',
                    token_data['access_token'],
                    timeout=3600
                )
                
                logger.info("Zoom access token refreshed")
                return token_data['access_token']
            else:
                logger.error(f"Zoom token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Zoom token refresh error: {e}")
            return None
    
    def get_user_info(self, access_token=None):
        """ユーザー情報を取得"""
        if not access_token:
            access_token = self.get_access_token()
            
        if not access_token:
            return None
            
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                'https://api.zoom.us/v2/users/me',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Zoom user info request failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Zoom user info error: {e}")
            return None