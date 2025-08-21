from django.db import models
from django.utils import timezone
import uuid


class CampaignTracking(models.Model):
    """キャンペーントラッキング用モデル"""

    class Source(models.TextChoices):
        FLYER = 'flyer', 'チラシ'
        WEB = 'web', 'Webサイト'
        SOCIAL = 'social', 'SNS'
        FRIEND = 'friend', '友人・知人の紹介'
        NEWS = 'news', 'ニュース・記事'
        OTHER = 'other', 'その他'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(
        max_length=50,
        choices=Source.choices,
        verbose_name='流入元'
    )
    session_id = models.CharField(
        max_length=255,
        verbose_name='セッションID',
        help_text='Cookieなどで管理するセッションID'
    )
    ip_address = models.GenericIPAddressField(
        verbose_name='IPアドレス',
        null=True,
        blank=True
    )
    user_agent = models.TextField(
        verbose_name='ユーザーエージェント',
        null=True,
        blank=True
    )
    referer = models.URLField(
        verbose_name='リファラー',
        null=True,
        blank=True,
        max_length=500
    )
    accessed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='アクセス日時'
    )
    registered_user = models.ForeignKey(
        'member_management.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_tracking',
        verbose_name='登録ユーザー'
    )
    registered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='登録日時'
    )
    is_manual_referral = models.BooleanField(
        default=False,
        verbose_name='手動設定',
        help_text='ユーザーが手動で流入元を選択した場合はTrue'
    )

    class Meta:
        verbose_name = 'キャンペーントラッキング'
        verbose_name_plural = 'キャンペーントラッキング'
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['source', 'accessed_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['registered_user']),
        ]

    def __str__(self):
        return f"{self.get_source_display()} - {self.session_id[:8]} ({self.accessed_at})"

    @classmethod
    def get_stats(cls, source=None):
        """統計情報を取得"""
        queryset = cls.objects.all()
        if source:
            queryset = queryset.filter(source=source)

        total_access = queryset.count()
        total_registered = queryset.filter(registered_user__isnull=False).count()
        conversion_rate = (total_registered / total_access * 100) if total_access > 0 else 0

        return {
            'total_access': total_access,
            'total_registered': total_registered,
            'conversion_rate': conversion_rate
        }