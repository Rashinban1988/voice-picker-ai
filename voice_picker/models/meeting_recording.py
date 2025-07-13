from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid
from member_management.models import Organization
from .uploaded_file import UploadedFile


class MeetingRecordingStatus(models.IntegerChoices):
    PENDING = 0, _('待機中')
    RECORDING = 1, _('録画中')
    COMPLETED = 2, _('録画完了')
    FAILED = 3, _('録画失敗')


class MeetingRecording(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='meeting_recordings',
        verbose_name='組織'
    )
    meeting_url = models.URLField(max_length=500, verbose_name='会議URL')
    meeting_title = models.CharField(max_length=200, null=True, blank=True, verbose_name='会議タイトル')
    scheduled_start_time = models.DateTimeField(verbose_name='開始予定時刻')
    actual_start_time = models.DateTimeField(null=True, blank=True, verbose_name='実際の開始時刻')
    actual_end_time = models.DateTimeField(null=True, blank=True, verbose_name='実際の終了時刻')

    # 録画ファイル関連
    uploaded_file = models.OneToOneField(
        UploadedFile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='meeting_recording',
        verbose_name='録画ファイル'
    )

    # 録画状態
    status = models.IntegerField(
        choices=MeetingRecordingStatus.choices,
        default=MeetingRecordingStatus.PENDING,
        verbose_name='録画状態'
    )

    # エラー情報
    error_message = models.TextField(null=True, blank=True, verbose_name='エラーメッセージ')

    # 録画設定
    recording_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='録画設定'
    )

    # タイムスタンプ
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    exist = models.BooleanField(default=True, verbose_name='存在')

    def delete(self, using=None, keep_parents=False):
        """論理削除"""
        self.deleted_at = timezone.now()
        self.exist = False
        self.save()

    def is_exist(self):
        """存在チェック"""
        return self.exist

    def is_recording_completed(self):
        """録画完了チェック"""
        return self.status == MeetingRecordingStatus.COMPLETED

    def is_recording_failed(self):
        """録画失敗チェック"""
        return self.status == MeetingRecordingStatus.FAILED

    def get_recording_duration(self):
        """録画時間の取得"""
        if self.actual_start_time and self.actual_end_time:
            return (self.actual_end_time - self.actual_start_time).total_seconds()
        return None

    def __str__(self):
        return f"{self.meeting_title or 'Untitled Meeting'} - {self.scheduled_start_time}"

    class Meta:
        verbose_name = '会議録画'
        verbose_name_plural = '会議録画'
        ordering = ['-scheduled_start_time']
