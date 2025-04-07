from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone
from rest_framework import serializers
from .models import Organization, User

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        user.last_login = timezone.now()
        user.set_password(user.password)
        user.save()
        return token

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'last_name', 'first_name', 'phone_number', 'organization', 'is_active', 'is_admin', 'created_at', 'updated_at', 'deleted_at']
        extra_kwargs = {
            'username': {
                'required': False,
            },
            'password': {
                'required': False,
                'write_only': True,
            },
            'organization': {
                'required': False,
                'read_only': True,
            }
        }
