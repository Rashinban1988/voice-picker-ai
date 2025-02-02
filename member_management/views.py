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
from .serializers import CustomTokenObtainPairSerializer
from .models.user import User
from .models.organization import Organization
from .schemas import UserCreate, OrganizationCreate
import json
import logging
from decouple import config
logger = logging.getLogger('django')

class RegisterView(View):
    def post(self, request):
        # バリデーション
        try:
            # リクエストデータを一度だけバリデート
            data = json.loads(request.body)
            user_data = UserCreate(**data)
            organization_data = OrganizationCreate(**data)
        except ValueError as e:
            return JsonResponse({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # メールアドレスの重複チェック
        if User.objects.filter(email=user_data.email).exists():
            return JsonResponse({'message': 'メールアドレスが既に存在します'}, status=status.HTTP_400_BAD_REQUEST)

        # 組織を作成
        # トランザクション
        with transaction.atomic():
            try:
                organization = Organization.objects.create(
                    name=organization_data.name,
                    phone_number=organization_data.phone_number
                )

                # ユーザーを作成
                user = User(username=user_data.email, last_name=user_data.sei, first_name=user_data.mei, email=user_data.email, phone_number=user_data.phone_number, organization=organization)
                user.set_password(user_data.password)  # パスワードをハッシュ化して設定
                user.save()

                # メールアドレスの確認メールを送信
                self.send_verification_email(user)

            except Exception as e:
                transaction.rollback()
                logger.info('ユーザーが作成できませんでした')
                logger.info(e)
                return JsonResponse({'message': 'ユーザーが作成できませんでした'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response =  {
            'organization' : organization.id,
            'user' : user.id,
            'message' : 'メール認証リンクを送信しました。',
        }
        return JsonResponse(response, status=status.HTTP_201_CREATED)

    def send_verification_email(self, user):
        subject = '【Voice Picker AI】メールアドレスの確認'
        verification_link = reverse('verify_email', kwargs={'uidb64': urlsafe_base64_encode(force_bytes(user.pk))})
        message = f'以下のリンクをクリックしてメールアドレスを確認してください:\n{config("APP_HOST")}:{config("APP_PORT")}{verification_link}'

        send_mail(
            subject=subject,
            message=message,
            from_email='support@rakumanu.com',
            recipient_list=[user.email],
            fail_silently=False,
        )

    def verify_email(request, uidb64):
        if request.method == 'GET':
            user_id = urlsafe_base64_decode(uidb64).decode()
            user = get_object_or_404(User, pk=user_id)
            user.email_verified_at = timezone.now()
            user.is_active = True  # ユーザーをアクティブにする
            user.save()
            return JsonResponse({'message': 'メールアドレスが確認されました。'}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'message': '不正なリクエストです。'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

class LoginView(View):
    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            user.last_login_at = timezone.now()  # 最終ログイン時間を更新
            user.save()

            organization = Organization.objects.get(id=user.organization_id)

            return JsonResponse({
                'organization_id': organization.id,
                'access_token': user.auth_token.key,  # トークンを取得
                'token_type': 'Bearer',
            })
        return JsonResponse({'message': 'ログイン情報が正しくありません'}, status=401)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer