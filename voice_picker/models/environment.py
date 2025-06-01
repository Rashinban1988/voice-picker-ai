from django.db import models
from .uploaded_file import UploadedFile
from django.utils import timezone
import uuid
from django.utils.translation import gettext_lazy as _

class Environment(models.Model):
    """環境設定を管理するモデル"""
    code = models.CharField(max_length=50, unique=True, verbose_name='コード')
    value = models.TextField(blank=True, null=True, verbose_name='値')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    exist = models.BooleanField(default=True, verbose_name='存在')

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_exist = False
        self.save()

    def is_exist(self):
        return self.exist

    def __str__(self):
        return f"{self.code}: {self.value}"

    class Meta:
        verbose_name = _('environment')
        verbose_name_plural = _('environments')
        ordering = ['-updated_at']