from django.db import models
from django.utils import timezone
import uuid
from .organization import Organization


class SubscriptionPlan(models.Model):
    """サブスクリプションプランのモデル"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='プラン名')
    description = models.TextField(verbose_name='説明')
    price = models.IntegerField(verbose_name='価格（月額円）')
    max_duration = models.IntegerField(verbose_name='最大時間（分）', default=100)
    stripe_price_id = models.CharField(max_length=100, verbose_name='Stripe料金ID')
    is_active = models.BooleanField(default=True, verbose_name='有効')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    def __str__(self):
        return f"{self.name} ({self.price}円/月)"

    class Meta:
        verbose_name = 'サブスクリプションプラン'
        verbose_name_plural = 'サブスクリプションプラン'


class Subscription(models.Model):
    """組織のサブスクリプション情報のモデル"""
    class Status(models.IntegerChoices):
        INACTIVE = 0, '未契約'
        ACTIVE = 1, '有効'
        PAST_DUE = 2, '支払い遅延'
        CANCELED = 3, 'キャンセル'
        TRIAL = 4, 'トライアル'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='subscription', 
        verbose_name='組織'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subscriptions', 
        verbose_name='プラン'
    )
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.INACTIVE,
        verbose_name='ステータス'
    )
    stripe_customer_id = models.CharField(
        max_length=100, 
        verbose_name='Stripe顧客ID',
        blank=True,
        null=True
    )
    stripe_subscription_id = models.CharField(
        max_length=100, 
        verbose_name='Stripeサブスクリプション ID',
        blank=True,
        null=True
    )
    current_period_start = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='現在の期間開始日'
    )
    current_period_end = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='現在の期間終了日'
    )
    cancel_at_period_end = models.BooleanField(
        default=False, 
        verbose_name='期間終了時に解約'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')

    def __str__(self):
        return f"{self.organization.name}のサブスクリプション"

    class Meta:
        verbose_name = 'サブスクリプション'
        verbose_name_plural = 'サブスクリプション'

    def is_active(self):
        return self.status == self.Status.ACTIVE or self.status == self.Status.TRIAL

    def is_within_contract_period(self):
        """現在の時刻が契約期間内にあるかどうかを判定"""
        now = timezone.now()
        if self.current_period_start and self.current_period_end:
            return self.current_period_start <= now <= self.current_period_end
        return False
