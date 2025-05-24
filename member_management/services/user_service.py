from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from decouple import config
from django.utils import timezone
from django.shortcuts import redirect
from django.utils.http import urlsafe_base64_decode
from django.conf import settings
from member_management.models import User
from member_management.schemas import UserCreateData
from django.contrib.auth.hashers import make_password
import logging
api_logger = logging.getLogger('api')

class UserService:
    def __init__(self, organization):
        self.organization = organization

    def create_user(self, user_data: UserCreateData, is_register_view: bool = False) -> User:
        """ユーザー作成"""
        return self.organization.users.create(
            username=user_data.email,
            password=make_password(user_data.password),
            last_name=user_data.last_name,
            first_name=user_data.first_name,
            email=user_data.email,
            phone_number=user_data.phone_number,
            is_admin=is_register_view,
        )

    @staticmethod
    def send_verification_email(user):
        subject = '【Voice Picker AI】メールアドレスの確認'
        verification_link = reverse('verify_email', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(user.pk))
        })
        message = f'以下のリンクをクリックしてメールアドレスを確認してください:\n{config("APP_HOST")}{verification_link}'

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )

    @staticmethod
    def verify_email(request, uidb64):
        if request.method == 'GET':
            user_id = urlsafe_base64_decode(uidb64).decode()
            updated = User.objects.filter(pk=user_id).update(
                email_verified_at=timezone.now(),
                is_active=True
            )
            if not updated:
                return redirect(f'{settings.NEXT_JS_HOST}/auth/register-failed?error=user_not_found')

            return redirect(f'{settings.NEXT_JS_HOST}/auth/register-success')
        else:
            return redirect(f'{settings.NEXT_JS_HOST}/auth/register-failed?error=invalid_request')

    @staticmethod
    def increment_login_attempts(user: User) -> None:
        """ログイン試行回数を増やす"""
        user.login_attempts += 1
        if user.login_attempts >= 10:
            user.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        user.save()
        api_logger.info(f"Login attempts incremented for user {user.email}. Current attempts: {user.login_attempts}")

    @staticmethod
    def reset_login_attempts(user: User) -> None:
        """ログイン試行回数をリセット"""
        user.login_attempts = 0
        user.locked_until = None
        user.save()
        api_logger.info(f"Login attempts reset for user {user.email}")

    @staticmethod
    def is_locked(user: User) -> bool:
        """アカウントがロックされているか確認"""
        if user.locked_until and timezone.now() < user.locked_until:
            return True
        if user.locked_until and timezone.now() >= user.locked_until:
            UserService.reset_login_attempts(user)
        return False

    @staticmethod
    def send_two_factor_code(user: User, code: str) -> None:
        """2要素認証コードを送信"""
        if user.two_factor_method == 'email':
            subject = '【Voice Picker AI】認証コード'
            message = f'認証コード: {code}'

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=False,
            )
            api_logger.info(f"Two-factor code sent via email to {user.email}")
        else:  # SMS
            # SMS送信の実装（Twilio等のサービスを使用）
            api_logger.info(f"Two-factor code sent via SMS to {user.phone_number}")