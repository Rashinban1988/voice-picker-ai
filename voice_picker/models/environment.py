
from django.db import models
from .uploaded_file import UploadedFile
from django.utils import timezone
import uuid

class Environment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(_('code'), max_length=50, primary_key=True, verbose_name='コード')
    value = models.TextField(_('value'), blank=True, null=True, verbose_name='値')

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
        return self.name

    class Meta:
        verbose_name = '環境'