from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ABTestEvent(models.Model):
    """A/Bテストイベントを記録するモデル"""
    
    VARIANT_CHOICES = [
        ('A', 'Variant A'),
        ('B', 'Variant B'),
    ]
    
    EVENT_CHOICES = [
        ('page_view', 'Page View'),
        ('register_click', 'Register Click'),
        ('login_click', 'Login Click'),
        ('conversion', 'Conversion'),
    ]
    
    variant = models.CharField(
        max_length=1, 
        choices=VARIANT_CHOICES,
        help_text='A/Bテストのバリアント'
    )
    event = models.CharField(
        max_length=20, 
        choices=EVENT_CHOICES,
        help_text='イベントタイプ'
    )
    timestamp = models.BigIntegerField(
        help_text='フロントエンドから送信されたタイムスタンプ'
    )
    session_id = models.CharField(
        max_length=100,
        help_text='セッションID'
    )
    user_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text='ユーザーID（コンバージョン時のみ）'
    )
    ip_address = models.GenericIPAddressField(
        null=True, 
        blank=True,
        help_text='IPアドレス（統計用）'
    )
    user_agent = models.TextField(
        null=True, 
        blank=True,
        help_text='ユーザーエージェント（統計用）'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='レコード作成日時'
    )
    
    class Meta:
        db_table = 'ab_test_events'
        verbose_name = 'A/Bテストイベント'
        verbose_name_plural = 'A/Bテストイベント'
        indexes = [
            models.Index(fields=['variant', 'event'], name='idx_variant_event'),
            models.Index(fields=['timestamp'], name='idx_timestamp'),
            models.Index(fields=['session_id'], name='idx_session_id'),
            models.Index(fields=['created_at'], name='idx_created_at'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.variant} - {self.event} - {self.session_id}'


class ABTestSession(models.Model):
    """A/Bテストセッション情報を管理するモデル"""
    
    session_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='セッションID'
    )
    variant = models.CharField(
        max_length=1, 
        choices=ABTestEvent.VARIANT_CHOICES,
        help_text='このセッションに割り当てられたバリアント'
    )
    first_visit = models.DateTimeField(
        default=timezone.now,
        help_text='初回訪問日時'
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text='最終活動日時'
    )
    converted = models.BooleanField(
        default=False,
        help_text='コンバージョン済みフラグ'
    )
    conversion_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text='コンバージョン日時'
    )
    
    class Meta:
        db_table = 'ab_test_sessions'
        verbose_name = 'A/Bテストセッション'
        verbose_name_plural = 'A/Bテストセッション'
        indexes = [
            models.Index(fields=['variant'], name='idx_session_variant'),
            models.Index(fields=['converted'], name='idx_session_converted'),
            models.Index(fields=['first_visit'], name='idx_session_first_visit'),
        ]
        ordering = ['-first_visit']
    
    def __str__(self):
        return f'{self.session_id} - {self.variant} - {"Converted" if self.converted else "Not Converted"}'


class ABTestSummary(models.Model):
    """A/Bテスト結果の日次サマリー"""
    
    date = models.DateField(
        help_text='集計対象日'
    )
    variant = models.CharField(
        max_length=1, 
        choices=ABTestEvent.VARIANT_CHOICES,
        help_text='バリアント'
    )
    page_views = models.IntegerField(
        default=0,
        help_text='ページビュー数'
    )
    register_clicks = models.IntegerField(
        default=0,
        help_text='登録ボタンクリック数'
    )
    login_clicks = models.IntegerField(
        default=0,
        help_text='ログインボタンクリック数'
    )
    conversions = models.IntegerField(
        default=0,
        help_text='コンバージョン数'
    )
    unique_sessions = models.IntegerField(
        default=0,
        help_text='ユニークセッション数'
    )
    conversion_rate = models.FloatField(
        default=0.0,
        help_text='コンバージョン率'
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        db_table = 'ab_test_summary'
        verbose_name = 'A/Bテストサマリー'
        verbose_name_plural = 'A/Bテストサマリー'
        unique_together = ['date', 'variant']
        indexes = [
            models.Index(fields=['date', 'variant'], name='idx_summary_date_variant'),
            models.Index(fields=['date'], name='idx_summary_date'),
        ]
        ordering = ['-date', 'variant']
    
    def __str__(self):
        return f'{self.date} - {self.variant} - {self.page_views} views'