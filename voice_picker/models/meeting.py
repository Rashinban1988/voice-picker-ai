from django.db import models
from django.utils import timezone
import uuid
from member_management.models import Organization

class MeetingStatus(models.IntegerChoices):
    SCHEDULED = 0, '予定'
    RECORDING = 1, '録画中'
    COMPLETED = 2, '完了'
    ERROR = 3, 'エラー'

class Meeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='meetings', verbose_name='組織')
    meeting_url = models.URLField(verbose_name='ミーティングURL')
    meeting_platform = models.CharField(
        max_length=20,
        choices=[('zoom', 'Zoom'), ('teams', 'Teams'), ('meet', 'Google Meet')],
        verbose_name='プラットフォーム'
    )
    scheduled_time = models.DateTimeField(verbose_name='開始予定時刻')
    duration_minutes = models.IntegerField(default=60, verbose_name='録画時間（分）')
    status = models.IntegerField(
        choices=MeetingStatus.choices,
        default=MeetingStatus.SCHEDULED,
        verbose_name='ステータス'
    )
    recorded_file_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='録画ファイルパス')
    uploaded_file = models.ForeignKey('UploadedFile', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='アップロードファイル')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    exist = models.BooleanField(default=True, verbose_name='存在')

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.exist = False
        self.save()

    def is_exist(self):
        return self.exist

    def __str__(self):
        return f"{self.meeting_platform} - {self.scheduled_time}"

    class Meta:
        verbose_name = 'ミーティング'
        verbose_name_plural = 'ミーティング'
