from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone
from rest_framework import serializers
from .models import Organization, User, SubscriptionPlan, Subscription

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        user.last_login = timezone.now()
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

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'description', 'price', 'max_duration', 'is_active']

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'organization', 'plan', 'status', 
            'current_period_start', 'current_period_end', 
            'cancel_at_period_end', 'created_at', 'updated_at'
        ]
