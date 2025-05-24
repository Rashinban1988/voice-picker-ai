from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin
)
from .organization import Organization
import uuid

class CustomUserManager(BaseUserManager):
    def create_superuser(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError('The username must be set.')
        if not email:
            raise ValueError('The email must be set.')
        if not password:
            raise ValueError('The password must be set.')

        extra_fields.setdefault('is_active', True)

        user = self.create_user(username, email, password, **extra_fields)
        user.is_superuser = True
        user.is_staff = True
        user.save()

        return user

    def get_queryset_by_login_user(self, user):
        """
        ユーザーの権限に基づいて適切なクエリセットを返す
        """
        # 運営の場合は全ユーザーのデータを返す
        if user.is_staff or user.is_superuser:
            return self.all()

        # 組織管理者の場合は組織のユーザーのデータを返す
        if user.is_admin:
            return self.filter(organization=user.organization)

        # 一般ユーザーの場合は自分のデータのみ返す
        return self.filter(id=user.id)

class User(AbstractBaseUser, PermissionsMixin):
    username_validator = UnicodeUsernameValidator()

    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users', verbose_name='組織')
    username = models.CharField(db_index=True, max_length=50, unique=True)
    last_name = models.CharField(max_length=50, verbose_name='姓')
    first_name = models.CharField(max_length=50, verbose_name='名')
    email = models.EmailField(unique=True, verbose_name='メールアドレス')
    email_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='メールアドレス確認日時')
    password = models.CharField(max_length=255, verbose_name='パスワード')
    phone_number = models.CharField(max_length=15, unique=True, verbose_name='電話番号')
    is_admin = models.BooleanField(default=False, verbose_name='管理者')
    is_active = models.BooleanField(default=False, verbose_name='アクティブ')
    is_superuser = models.BooleanField(default=False, verbose_name='スーパーユーザー')
    is_staff = models.BooleanField(default=False, verbose_name='スタッフ')

    token = models.CharField(max_length=255, null=True, blank=True, verbose_name='トークン')

    # 2要素認証関連のフィールド
    two_factor_enabled = models.BooleanField(default=False, verbose_name='2要素認証有効')
    two_factor_method = models.CharField(
        max_length=10,
        choices=[('email', 'メール'), ('sms', 'SMS')],
        default='email',
        verbose_name='2要素認証方法'
    )

    # アカウントロック関連のフィールド
    login_attempts = models.IntegerField(default=0, verbose_name='ログイン試行回数')
    locked_until = models.DateTimeField(null=True, blank=True, verbose_name='ロック解除時刻')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    exist = models.BooleanField(default=True, verbose_name='存在')

    # ログイン時に使用するField
    USERNAME_FIELD = 'username'
    # 必要なField
    REQUIRED_FIELDS = ['email', 'password', 'phone_number', 'organization']

    # Custom User objectsを管理するためのManagerクラス
    objects = CustomUserManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_password = None  # 初期化

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.exist = False
        self.save()

    def is_exist(self):
        return self.exist

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.email})"

    class Meta:
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'
