from django.db import models
from django.db.models.signals import pre_save, post_delete
from django.utils import timezone
from django.dispatch import receiver
import os
import uuid
from member_management.models import Organization
from django.utils.translation import gettext_lazy as _

def organization_upload_to(instance, filename):
    """
    組織IDベースのディレクトリ構造でファイルを保存
    重複ファイル名を避けるため、必要に応じてファイル名を変更
    """
    organization_id = str(instance.organization.id)
    
    name, ext = os.path.splitext(filename)
    
    base_path = os.path.join(organization_id, filename)
    counter = 1
    
    while UploadedFile.objects.filter(
        organization=instance.organization,
        file__endswith=f"/{filename}" if counter == 1 else f"/{name}_{counter}{ext}"
    ).exists():
        filename = f"{name}_{counter}{ext}"
        counter += 1
    
    return os.path.join(organization_id, filename)

class UploadedFile(models.Model):
    class Status(models.IntegerChoices):
        UNPROCESSED = 0, _('未処理')
        PROCESSING = 1, _('処理中')
        COMPLETED = 2, _('処理済み')
        ERROR = 3, _('エラー')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='uploaded_files', verbose_name='組織')
    file = models.FileField(upload_to=organization_upload_to, verbose_name='ファイル')
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.UNPROCESSED,
        verbose_name='ステータス'
    )
    duration = models.FloatField(null=True, blank=True, verbose_name='再生時間（秒）')  # 再生時間（秒）
    summarization = models.TextField(null=True, blank=True, verbose_name='文書要約結果')  # 文書要約結果
    issue = models.TextField(null=True, blank=True, verbose_name='課題点')  # 課題点
    solution = models.TextField(null=True, blank=True, verbose_name='取り組み案')  # 取り組み案
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    exist = models.BooleanField(default=True, verbose_name='存在')
    hls_playlist_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='HLSプレイリストパス')
    
#     # Zoom会議録画用フィールド
#     source_type = models.CharField(max_length=20, default='upload', verbose_name='ソース種別')  # 'upload', 'zoom_meeting', 'scheduled_recording'
#     meeting_url = models.URLField(null=True, blank=True, verbose_name='会議URL')
#     meeting_number = models.CharField(max_length=20, null=True, blank=True, verbose_name='会議番号')
#     meeting_topic = models.CharField(max_length=255, null=True, blank=True, verbose_name='会議タイトル')
#     zoom_session_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='ZoomセッションID')
#     recording_start_time = models.DateTimeField(null=True, blank=True, verbose_name='録画開始時刻')
#     recording_end_time = models.DateTimeField(null=True, blank=True, verbose_name='録画終了時刻')
#     bot_process_id = models.IntegerField(null=True, blank=True, verbose_name='ボットプロセスID')
    
#     # 予約録画用フィールド
#     scheduled_start_time = models.DateTimeField(null=True, blank=True, verbose_name='予約開始時刻')
#     is_scheduled = models.BooleanField(default=False, verbose_name='予約録画フラグ')
#     meeting_details = models.JSONField(default=dict, blank=True, verbose_name='会議詳細情報')

    @property
    def transcriptions(self):
        from .transcription import Transcription
        return Transcription.objects.filter(uploaded_file=self)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.exist = False
        self.transcriptions.all().delete()
        self.save()

    def is_exist(self):
        return self.exist

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
                if old_file and os.path.isfile(old_file.path):
                    other_files_using_same_path = UploadedFile.objects.filter(
                        file=old_file.name
                    ).exclude(pk=instance.pk).exists()
                    
                    if not other_files_using_same_path:
                        os.remove(old_file.path)

# ファイルの削除
@receiver(post_delete, sender=UploadedFile)
def delete_file_on_delete(sender, instance, **kwargs):
    if instance.file:
        if os.path.isfile(instance.file.path):
            other_files_using_same_path = UploadedFile.objects.filter(
                file=instance.file.name
            ).exists()
            
            if not other_files_using_same_path:
                os.remove(instance.file.path)
                
                try:
                    dir_path = os.path.dirname(instance.file.path)
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except OSError:
                    pass
