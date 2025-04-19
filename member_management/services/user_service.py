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
        message = f'以下のリンクをクリックしてメールアドレスを確認してください:\n{config("APP_HOST")}:{config("APP_PORT")}{verification_link}'

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
                return redirect(f'{settings.NEXT_JS_HOST}:{settings.NEXT_JS_PORT}/auth/register-failed?error=user_not_found')

            return redirect(f'{settings.NEXT_JS_HOST}:{settings.NEXT_JS_PORT}/auth/register-success')
        else:
            return redirect(f'{settings.NEXT_JS_HOST}:{settings.NEXT_JS_PORT}/auth/register-failed?error=invalid_request')
