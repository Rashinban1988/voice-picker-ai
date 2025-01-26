from django.db import models
from django.db.models.signals import pre_save, post_delete
from django.utils import timezone
from django.dispatch import receiver
import os
import uuid
from member_management.models import Organization
from django.utils.translation import gettext_lazy as _

class Status(models.TextChoices):
    UNPROCESSED = 0, _('未処理')
    IN_PROGRESS = 1, _('処理中')
    PROCESSED = 2, _('処理済み')
    ERROR = 3, _('エラー')

class UploadedFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='uploaded_files', verbose_name='組織')
    file = models.FileField(upload_to='', verbose_name='ファイル')
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.UNPROCESSED,
        verbose_name='ステータス'
    )
    summarization = models.TextField(null=True, blank=True, verbose_name='文書要約結果')  # 文書要約結果
    issue = models.TextField(null=True, blank=True, verbose_name='課題点')  # 課題点
    solution = models.TextField(null=True, blank=True, verbose_name='取り組み案')  # 取り組み案
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    is_exist = models.BooleanField(default=True, verbose_name='存在')

    def transcriptions(self):
        from .transcription import Transcription
        return Transcription.objects.filter(uploaded_file=self)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_exist = False
        self.transcriptions.all().delete()
        self.save()

    def is_exist(self):
        return self.is_exist

    # その他の必要なフィールド
    def __str__(self):
        return self.file.name

    class Meta:
        verbose_name = 'アップロードファイル'
        verbose_name_plural = 'アップロードファイル'

# ファイルの更新
@receiver(pre_save, sender=UploadedFile)
def delete_old_file(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_file = UploadedFile.objects.get(pk=instance.pk).file
        except UploadedFile.DoesNotExist:
            return
        else:
            new_file = instance.file
            if not old_file == new_file:
                if os.path.isfile(old_file.path):
                    os.remove(old_file.path)

# ファイルの削除
@receiver(post_delete, sender=UploadedFile)
def delete_file_on_delete(sender, instance, **kwargs):
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)