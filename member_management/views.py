from django.db import transaction
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import authenticate, login
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.urls import reverse
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views import View
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from member_management.services import AuthService, UserService, OrganizationService
from .serializers import CustomTokenObtainPairSerializer, OrganizationSerializer, UserSerializer
from .models import User, Organization
from .schemas import UserCreateData, OrganizationCreateData
import json
import logging
from decouple import config

api_logger = logging.getLogger('django')

class RegisterView(View):
    def post(self, request):
        api_logger.info(f"Register request: {request.POST}")
        request_data = json.loads(request.body)

        try:
            organization_data = OrganizationCreateData(**request_data)
            user_data = UserCreateData(**request_data)

            with transaction.atomic():
                organization = OrganizationService.create_organization(organization_data)
                user_service = UserService(organization)
                user = user_service.create_user(user_data, is_register_view=True)

                try:
                    UserService.send_verification_email(user)
                except Exception as e:
                    api_logger.error(f"User registration email sending failed: {e}")
                    raise

            api_logger.info(f"User registration successful: {user.id}")
            return JsonResponse({'message': 'メール認証リンクを送信しました。'}, status=status.HTTP_201_CREATED)

        except ValueError as e:
            api_logger.error(f"User registration validation error: {e}")
            return JsonResponse({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            api_logger.error(f"User registration failed: {e}")
            return JsonResponse({'message': 'ユーザーが作成できませんでした'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmailVerificationView(View):
    def get(self, request, uidb64):
        try:
            return UserService.verify_email(request, uidb64)
        except Exception as e:
            return JsonResponse({'message': 'メール認証に失敗しました'}, status=status.HTTP_400_BAD_REQUEST)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer