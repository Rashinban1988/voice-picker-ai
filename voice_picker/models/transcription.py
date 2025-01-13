from django.db import models
from .uploaded_file import UploadedFile
from django.utils import timezone
import uuid

class Transcription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name='transcription', verbose_name='アップロードファイル')
    start_time = models.IntegerField(verbose_name='開始時間（秒）')  # 開始時間（秒）
    text = models.TextField(verbose_name='文字起こしテキスト')  # 文字起こしテキスト

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    is_exist = models.BooleanField(default=True, verbose_name='存在')

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_exist = False
        self.save()

    def is_exist(self):
        return self.is_exist

    # その他の必要なフィールド
    def __str__(self):
        return self.text

    class Meta:
        verbose_name = '文字起こしテキスト'
        verbose_name_plural = '文字起こしテキスト'
