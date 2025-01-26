from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models.user import User
from django.http import JsonResponse
from rest_framework import status
from typing import Dict, Any
import logging

logger = logging.getLogger('django')

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def get_token(cls, user: User):
        try:
            logger.info('トークン取得します')
            token = super().get_token(user) # トークン取得
            logger.info('トークン取得に成功しました: %s', str(token))
        except Exception as e:
            logger.error('トークン取得に失敗しました: %s', str(e))
            raise e

        return token

    def validate(self, attrs: Dict[str, Any]):
        logger.info('バリデートします')
        data = super().validate(attrs)
        logger.info('バリデートに成功しました: %s', str(data))
        refresh = self.get_token(self.user)
        logger.info('リフレッシュトークン取得に成功しました: %s', str(refresh))
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        logger.info('アクセストークン取得に成功しました: %s', str(data['access']))
        return data