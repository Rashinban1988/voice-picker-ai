from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models.organization import Organization
from .models.user import User
from django.http import JsonResponse
from rest_framework import status
from typing import Dict, Any
import logging

logger = logging.getLogger('django')

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # カスタムクレームを追加
        organization = user.organization
        if organization:
            token['organization_id'] = str(organization.id)

        return token

    def validate(self, attrs: Dict[str, Any]):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        data['organization_id'] = str(self.user.organization.id)
        return data

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'organization', 'username', 'last_name', 'first_name', 'email', 'phone_number', 'is_admin', 'is_active', 'created_at', 'updated_at', 'deleted_at']
