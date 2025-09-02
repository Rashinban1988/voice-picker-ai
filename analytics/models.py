from django.db import models
from django.utils import timezone
import uuid


class TrackingProject(models.Model):
    """LP分析プロジェクト"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='プロジェクト名')
    tracking_id = models.CharField(max_length=50, unique=True, verbose_name='トラッキングID')
    domain = models.URLField(verbose_name='対象ドメイン')
    organization = models.ForeignKey(
        'member_management.Organization',
        on_delete=models.CASCADE,
        related_name='tracking_projects',
        verbose_name='組織'
    )
    is_active = models.BooleanField(default=True, verbose_name='有効')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    def __str__(self):
        return f"{self.name} ({self.tracking_id})"

    class Meta:
        verbose_name = 'トラッキングプロジェクト'
        verbose_name_plural = 'トラッキングプロジェクト'


class PageView(models.Model):
    """ページビュー"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        TrackingProject,
        on_delete=models.CASCADE,
        related_name='page_views',
        verbose_name='プロジェクト'
    )
    session_id = models.CharField(max_length=100, verbose_name='セッションID')
    page_url = models.URLField(verbose_name='ページURL')
    page_title = models.CharField(max_length=200, null=True, blank=True, verbose_name='ページタイトル')
    referrer = models.URLField(null=True, blank=True, verbose_name='参照元URL')
    user_agent = models.TextField(verbose_name='ユーザーエージェント')
    ip_address = models.GenericIPAddressField(verbose_name='IPアドレス')
    screen_width = models.IntegerField(null=True, blank=True, verbose_name='画面幅')
    screen_height = models.IntegerField(null=True, blank=True, verbose_name='画面高')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    class Meta:
        verbose_name = 'ページビュー'
        verbose_name_plural = 'ページビュー'
        indexes = [
            models.Index(fields=['project', 'created_at']),
            models.Index(fields=['session_id']),
        ]


class UserInteraction(models.Model):
    """ユーザーインタラクション"""
    class EventType(models.TextChoices):
        CLICK = 'click', 'クリック'
        SCROLL = 'scroll', 'スクロール'
        MOUSEMOVE = 'mousemove', 'マウス移動'
        MOUSEENTER = 'mouseenter', 'マウス進入'
        MOUSELEAVE = 'mouseleave', 'マウス離脱'
        RESIZE = 'resize', 'ウィンドウサイズ変更'
        FOCUS = 'focus', 'フォーカス'
        BLUR = 'blur', 'フォーカス離脱'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page_view = models.ForeignKey(
        PageView,
        on_delete=models.CASCADE,
        related_name='interactions',
        verbose_name='ページビュー'
    )
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        verbose_name='イベントタイプ'
    )
    x_coordinate = models.IntegerField(null=True, blank=True, verbose_name='X座標')
    y_coordinate = models.IntegerField(null=True, blank=True, verbose_name='Y座標')
    scroll_percentage = models.FloatField(null=True, blank=True, verbose_name='スクロール率(%)')
    element_selector = models.TextField(null=True, blank=True, verbose_name='要素セレクタ')
    element_text = models.TextField(null=True, blank=True, verbose_name='要素テキスト')
    viewport_width = models.IntegerField(null=True, blank=True, verbose_name='ビューポート幅')
    viewport_height = models.IntegerField(null=True, blank=True, verbose_name='ビューポート高')
    timestamp = models.DateTimeField(verbose_name='イベント発生時刻')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')

    class Meta:
        verbose_name = 'ユーザーインタラクション'
        verbose_name_plural = 'ユーザーインタラクション'
        indexes = [
            models.Index(fields=['page_view', 'event_type']),
            models.Index(fields=['timestamp']),
        ]


class HeatmapData(models.Model):
    """ヒートマップ集計データ"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        TrackingProject,
        on_delete=models.CASCADE,
        related_name='heatmap_data',
        verbose_name='プロジェクト'
    )
    page_url = models.URLField(verbose_name='ページURL')
    x_coordinate = models.IntegerField(verbose_name='X座標')
    y_coordinate = models.IntegerField(verbose_name='Y座標')
    click_count = models.IntegerField(default=0, verbose_name='クリック数')
    hover_count = models.IntegerField(default=0, verbose_name='ホバー数')
    date = models.DateField(verbose_name='集計日')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    class Meta:
        verbose_name = 'ヒートマップデータ'
        verbose_name_plural = 'ヒートマップデータ'
        unique_together = ['project', 'page_url', 'x_coordinate', 'y_coordinate', 'date']
        indexes = [
            models.Index(fields=['project', 'page_url', 'date']),
        ]


class ScrollDepth(models.Model):
    """スクロール深度集計"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        TrackingProject,
        on_delete=models.CASCADE,
        related_name='scroll_depths',
        verbose_name='プロジェクト'
    )
    page_url = models.URLField(verbose_name='ページURL')
    depth_percentage = models.IntegerField(verbose_name='スクロール深度(%)')
    user_count = models.IntegerField(default=0, verbose_name='ユーザー数')
    date = models.DateField(verbose_name='集計日')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    class Meta:
        verbose_name = 'スクロール深度'
        verbose_name_plural = 'スクロール深度'
        unique_together = ['project', 'page_url', 'depth_percentage', 'date']
        indexes = [
            models.Index(fields=['project', 'page_url', 'date']),
        ]
