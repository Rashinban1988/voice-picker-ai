from django.db import models
from django.utils import timezone
from .uploaded_file import UploadedFile
import uuid

class ScheduledRecording(models.Model):
    """予約録画モデル"""
    
    STATUS_CHOICES = [
        ('scheduled', '予約済み'),
        ('preparing', '準備中'),
        ('recording', '録画中'),
        ('completed', '完了'),
        ('failed', '失敗'),
        ('cancelled', 'キャンセル'),
    ]
    
    RECORDING_TYPE_CHOICES = [
        ('immediate', '即時録画'),
        ('scheduled', '予約録画'),
        ('recurring', '定期録画'),
    ]
    
    # 基本情報
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name='scheduled_recordings')
    
    # 会議情報
    meeting_id = models.CharField(max_length=20, verbose_name='会議ID')
    meeting_topic = models.CharField(max_length=255, blank=True, verbose_name='会議タイトル')
    meeting_url = models.URLField(verbose_name='会議URL')
    meeting_password = models.CharField(max_length=50, blank=True, verbose_name='会議パスワード')
    host_email = models.EmailField(blank=True, verbose_name='主催者メール')
    
    # スケジュール情報
    scheduled_start_time = models.DateTimeField(verbose_name='予約開始時刻')
    scheduled_end_time = models.DateTimeField(null=True, blank=True, verbose_name='予約終了時刻')
    estimated_duration = models.IntegerField(default=60, verbose_name='予想時間（分）')
    timezone_name = models.CharField(max_length=50, default='Asia/Tokyo', verbose_name='タイムゾーン')
    
    # 録画設定
    recording_type = models.CharField(max_length=20, choices=RECORDING_TYPE_CHOICES, default='scheduled', verbose_name='録画種別')
    auto_start = models.BooleanField(default=True, verbose_name='自動開始')
    auto_stop = models.BooleanField(default=True, verbose_name='自動停止')
    pre_recording_minutes = models.IntegerField(default=5, verbose_name='録画開始前余裕時間（分）')
    post_recording_minutes = models.IntegerField(default=10, verbose_name='録画終了後余裕時間（分）')
    
    # 状態管理
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name='状態')
    celery_task_id = models.CharField(max_length=255, blank=True, verbose_name='CeleryタスクID')
    
    # 実行結果
    actual_start_time = models.DateTimeField(null=True, blank=True, verbose_name='実際の開始時刻')
    actual_end_time = models.DateTimeField(null=True, blank=True, verbose_name='実際の終了時刻')
    error_message = models.TextField(blank=True, verbose_name='エラーメッセージ')
    
    # 会議詳細情報（JSON）
    meeting_details = models.JSONField(default=dict, blank=True, verbose_name='会議詳細情報')
    
    # タイムスタンプ
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    
    class Meta:
        db_table = 'scheduled_recordings'
        verbose_name = '予約録画'
        verbose_name_plural = '予約録画'
        indexes = [
            models.Index(fields=['scheduled_start_time']),
            models.Index(fields=['status']),
            models.Index(fields=['meeting_id']),
        ]
    
    def __str__(self):
        return f"録画予約 {self.meeting_topic} ({self.scheduled_start_time})"
    
    @property
    def is_active(self):
        """アクティブな予約かどうか"""
        return self.status in ['scheduled', 'preparing', 'recording']
    
    @property
    def can_cancel(self):
        """キャンセル可能かどうか"""
        return self.status in ['scheduled', 'preparing'] and self.scheduled_start_time > timezone.now()
    
    @property
    def is_ready_to_start(self):
        """録画開始可能かどうか"""
        if self.status != 'scheduled':
            return False
        
        now = timezone.now()
        start_with_buffer = self.scheduled_start_time - timezone.timedelta(minutes=self.pre_recording_minutes)
        return now >= start_with_buffer
    
    @property
    def should_stop(self):
        """録画停止すべきかどうか"""
        if self.status != 'recording':
            return False
        
        if not self.auto_stop:
            return False
        
        now = timezone.now()
        stop_time = self.scheduled_end_time or (
            self.scheduled_start_time + timezone.timedelta(minutes=self.estimated_duration)
        )
        stop_with_buffer = stop_time + timezone.timedelta(minutes=self.post_recording_minutes)
        
        return now >= stop_with_buffer
    
    @property
    def recording_window(self):
        """録画ウィンドウ（開始から終了まで）"""
        start_time = self.scheduled_start_time - timezone.timedelta(minutes=self.pre_recording_minutes)
        end_time = self.scheduled_end_time or (
            self.scheduled_start_time + timezone.timedelta(minutes=self.estimated_duration)
        )
        end_time = end_time + timezone.timedelta(minutes=self.post_recording_minutes)
        
        return {
            'start': start_time,
            'end': end_time,
            'duration_minutes': int((end_time - start_time).total_seconds() / 60)
        }
    
    def update_status(self, new_status, error_message=None):
        """状態を更新"""
        self.status = new_status
        if error_message:
            self.error_message = error_message
        
        # 実行時刻を記録
        now = timezone.now()
        if new_status == 'recording' and not self.actual_start_time:
            self.actual_start_time = now
        elif new_status in ['completed', 'failed', 'cancelled'] and not self.actual_end_time:
            self.actual_end_time = now
        
        self.save()
    
    def cancel(self, reason=None):
        """予約をキャンセル"""
        if not self.can_cancel:
            raise ValueError("Cannot cancel this recording")
        
        self.update_status('cancelled', reason)
        
        # Celeryタスクもキャンセル
        if self.celery_task_id:
            from celery import current_app
            current_app.control.revoke(self.celery_task_id, terminate=True)
    
    def get_time_until_start(self):
        """開始までの残り時間"""
        if self.status != 'scheduled':
            return None
        
        now = timezone.now()
        if self.scheduled_start_time <= now:
            return timezone.timedelta(0)
        
        return self.scheduled_start_time - now
    
    def get_formatted_schedule(self):
        """スケジュールの整形済み文字列"""
        start_time = self.scheduled_start_time.strftime('%Y-%m-%d %H:%M')
        if self.scheduled_end_time:
            end_time = self.scheduled_end_time.strftime('%H:%M')
            return f"{start_time} - {end_time}"
        else:
            return f"{start_time} ({self.estimated_duration}分間)"