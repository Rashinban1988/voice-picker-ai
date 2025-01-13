from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from .organization import Organization
import uuid

class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users', verbose_name='組織')
    sei = models.CharField(max_length=255, verbose_name='姓')
    mei = models.CharField(max_length=255, verbose_name='名')
    email = models.EmailField(unique=True, verbose_name='メールアドレス')
    email_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='メールアドレス確認日時')
    password = models.CharField(max_length=255, verbose_name='パスワード')
    phone_number = models.CharField(max_length=15, unique=True, verbose_name='電話番号')
    is_admin = models.BooleanField(default=False, verbose_name='管理者')
    is_active = models.BooleanField(default=False, verbose_name='アクティブ')
    token = models.CharField(max_length=255, null=True, blank=True, verbose_name='トークン')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    is_exist = models.BooleanField(default=True, verbose_name='存在')

    def save(self, *args, **kwargs):
        # パスワードをハッシュ化
        if self.pk is None or self.password != self.__original_password:
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def set_password(self, password):
        self.password = password
        self.__original_password = password

    def check_password(self, password):
        return check_password(password, self.password)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_exist = False
        self.save()

    def is_exist(self):
        return self.is_exist

    def __str__(self):
        return f"{self.sei} {self.mei} ({self.email})"

    class Meta:
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'
