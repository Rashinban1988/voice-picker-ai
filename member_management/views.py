from django.db import transaction
from django.http import JsonResponse
from django.views import View
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import viewsets
from rest_framework.response import Response
from member_management.services import UserService, OrganizationService
from .serializers import CustomTokenObtainPairSerializer, OrganizationSerializer, UserSerializer
from .models import User, Organization
from .schemas import UserCreateData, OrganizationCreateData
import json
import logging

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

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.organization

        # 運営の場合は全組織のデータを返す
        if user.is_staff or user.is_superuser:
            return Organization.objects.all()

        # 管理者、一般ユーザーの場合は自分の組織のデータを返す
        return Organization.objects.filter(id=organization.id)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.organization

        # 運営の場合は全ユーザーのデータを返す
        if user.is_staff or user.is_superuser:
            return User.objects.all()

        # 組織管理者の場合は組織のユーザーのデータを返す
        elif user.is_admin:
            return User.objects.filter(organization=organization)

        # 一般ユーザーの場合は自分のデータのみ返す
        return User.objects.filter(id=user.id)

    def me(self, request):
        # 現在のユーザーの情報のみをシリアライズして返す
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class EmailVerificationView(View):
    def get(self, request, uidb64):
        try:
            return UserService.verify_email(request, uidb64)
        except Exception as e:
            return JsonResponse({'message': 'メール認証に失敗しました'}, status=status.HTTP_400_BAD_REQUEST)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer