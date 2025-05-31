from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from decouple import config
from django.utils import timezone
from django.shortcuts import redirect
from django.conf import settings
from member_management.models import User
from member_management.schemas import UserCreateData
from django.contrib.auth.hashers import make_password
import logging

# ロガーの設定
api_logger = logging.getLogger('api')

class UserService:
    """ユーザー関連のサービスを提供するクラス"""

    # 定数の定義
    MAX_LOGIN_ATTEMPTS = 10
    LOCK_DURATION_MINUTES = 30
    EMAIL_SUBJECT_VERIFICATION = '【Voice Picker AI】メールアドレス確認のお願い'
    EMAIL_SUBJECT_2FA = '【Voice Picker AI】認証コードのご案内'

    def __init__(self, organization):
        self.organization = organization

    def create_user(self, user_data: UserCreateData, is_register_view: bool = False) -> User:
        """ユーザーを作成する

        Args:
            user_data (UserCreateData): ユーザー作成に必要なデータ
            is_register_view (bool, optional): 登録画面からの作成かどうか. Defaults to False.

        Returns:
            User: 作成されたユーザーオブジェクト
        """
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
    def send_verification_email(user: User) -> None:
        """メール認証用のメールを送信する

        Args:
            user (User): メールを送信するユーザー
        """
        verification_link = reverse('verify_email', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(user.pk))
        })

        message = (
            f'Voice Picker AIをご利用いただき、ありがとうございます。\n\n'
            f'【メールアドレスの確認】\n\n'
            f'以下のリンクをクリックして、メールアドレスの確認をお願いいたします。\n'
            f'{config("APP_HOST")}{verification_link}\n\n'
            f'※このメールに心当たりがない場合は、念のため本メールを破棄してください。\n'
            f'本メールは自動送信されています。ご返信いただいても対応できませんのでご了承ください。\n\n'
            f'Voice Picker AI 運営事務局'
        )

        send_mail(
            subject=UserService.EMAIL_SUBJECT_VERIFICATION,
            message=message,
            from_email=f"{config('EMAIL_HOST_FROM')}",
            recipient_list=[user.email],
            fail_silently=False,
        )

    @staticmethod
    def verify_email(request, uidb64):
        """メール認証を実行する

        Args:
            request: リクエストオブジェクト
            uidb64: エンコードされたユーザーID

        Returns:
            redirect: 認証結果に応じたリダイレクト
        """
        if request.method != 'GET':
            return redirect(f'{settings.NEXT_JS_HOST}/auth/register-failed?error=invalid_request')

        try:
            user_id = urlsafe_base64_decode(uidb64).decode()
            updated = User.objects.filter(pk=user_id).update(
                email_verified_at=timezone.now(),
                is_active=True
            )

            if not updated:
                return redirect(f'{settings.NEXT_JS_HOST}/auth/register-failed?error=user_not_found')

            return redirect(f'{settings.NEXT_JS_HOST}/auth/register-success')

        except Exception as e:
            api_logger.error(f"Email verification failed: {str(e)}")
            return redirect(f'{settings.NEXT_JS_HOST}/auth/register-failed?error=verification_failed')

    @staticmethod
    def increment_login_attempts(user: User) -> None:
        """ログイン試行回数を増やす

        Args:
            user (User): 対象ユーザー
        """
        user.login_attempts += 1
        if user.login_attempts >= UserService.MAX_LOGIN_ATTEMPTS:
            user.locked_until = timezone.now() + timezone.timedelta(minutes=UserService.LOCK_DURATION_MINUTES)
        user.save()
        api_logger.info(f"Login attempts incremented for user {user.email}. Current attempts: {user.login_attempts}")

    @staticmethod
    def reset_login_attempts(user: User) -> None:
        """ログイン試行回数をリセット

        Args:
            user (User): 対象ユーザー
        """
        user.login_attempts = 0
        user.locked_until = None
        user.save()
        api_logger.info(f"Login attempts reset for user {user.email}")

    @staticmethod
    def is_locked(user: User) -> bool:
        """アカウントがロックされているか確認

        Args:
            user (User): 対象ユーザー

        Returns:
            bool: ロックされている場合はTrue
        """
        if user.locked_until and timezone.now() < user.locked_until:
            return True
        if user.locked_until and timezone.now() >= user.locked_until:
            UserService.reset_login_attempts(user)
        return False

    @staticmethod
    def send_two_factor_code(user: User, code: str) -> None:
        """2要素認証コードを送信

        Args:
            user (User): 対象ユーザー
            code (str): 認証コード
        """
        if user.two_factor_method == 'email':
            message = (
                f'Voice Picker AIをご利用いただき、ありがとうございます。\n\n'
                f'【認証コード】\n\n'
                f'以下のコードを入力して、本人確認を完了してください：\n'
                f'認証コード：{code}\n\n'
                f'※認証コードの有効期限は5分間です。\n'
                f'※認証コードの有効期限が切れた場合は、再度お手続きをお願いいたします。\n'
                f'※このメールに心当たりがない場合は、念のため本メールを破棄してください。\n'
                f'本メールは自動送信されています。ご返信いただいても対応できませんのでご了承ください。\n\n'
                f'Voice Picker AI 運営事務局'
            )
            send_mail(
                subject=UserService.EMAIL_SUBJECT_2FA,
                message=message,
                from_email=f"{config('EMAIL_HOST_FROM')}",
                recipient_list=[user.email],
                fail_silently=False,
            )
            api_logger.info(f"Two-factor code sent via email to {user.email}")
        else:  # SMS
            # SMS送信の実装（Twilio等のサービスを使用）
            api_logger.info(f"Two-factor code sent via SMS to {user.phone_number}")