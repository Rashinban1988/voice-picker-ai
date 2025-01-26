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
    """
    custom userの場合、custom User Managerを作成する必要がある。
    userとsuperuserを作る関数のみを上書きする。
    """
    def create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError('The username must be set.')
        if not email:
            raise ValueError('The email must be set.')
        if not password:
            raise ValueError('The password must be set.')

        user = self.model(username=username, email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save()

        return user

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

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    is_exist = models.BooleanField(default=True, verbose_name='存在')

    # ログイン時に使用するField
    USERNAME_FIELD = 'username'
    # 必要なField
    REQUIRED_FIELDS = ['email', 'password', 'phone_number', 'organization']

    # Custom User objectsを管理するためのManagerクラス
    objects = CustomUserManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_password = None  # 初期化

    def save(self, *args, **kwargs):
        # パスワードをハッシュ化
        if self.pk is None or self.password != self.__original_password:
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def set_password(self, password):
        self.__original_password = password
        self.password = password

    def check_password(self, password):
        return check_password(password, self.password)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_exist = False
        self.save()

    def is_exist(self):
        return self.is_exist

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.email})"

    class Meta:
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'
