from django.contrib import admin
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.urls import path
from .models.organization import Organization
from .models.user import User
from .models.subscription import Subscription, SubscriptionPlan
from .models.campaign_tracking import CampaignTracking
from voice_picker.models import Environment, ScheduledRecording
from analytics.models import TrackingProject, PageView, UserInteraction
from analytics.admin import TrackingProjectAdmin, PageViewAdmin, UserInteractionAdmin

# スーパーユーザーのみがアクセスできるデコレーター
def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone_number', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['name', 'phone_number']

class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'organization', 'last_name', 'first_name', 'email', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['last_name', 'first_name', 'email']

class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'max_duration', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'stripe_price_id']

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'plan', 'status', 'current_period_start', 'current_period_end', 'created_at']
    list_filter = ['status', 'created_at', 'cancel_at_period_end']
    search_fields = ['organization__name', 'stripe_customer_id', 'stripe_subscription_id']

class EnvironmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'value', 'exist', 'created_at', 'updated_at']
    list_filter = ['exist', 'created_at']
    search_fields = ['code', 'value']

class ScheduledRecordingAdmin(admin.ModelAdmin):
    list_display = ['id', 'meeting_topic', 'status', 'scheduled_start_time', 'created_at', 'updated_at']
    list_filter = ['status', 'recording_type', 'created_at']
    search_fields = ['meeting_topic', 'meeting_id', 'host_email']

class CampaignTrackingAdmin(admin.ModelAdmin):
    """キャンペーントラッキング管理"""
    list_display = ['id_short', 'source_badge', 'session_id_short', 'accessed_at', 'registered_status', 'registered_user_link', 'conversion_time']
    list_filter = ['source', 'accessed_at', ('registered_user', admin.EmptyFieldListFilter)]
    search_fields = ['session_id', 'ip_address', 'registered_user__email', 'registered_user__last_name', 'registered_user__first_name']
    date_hierarchy = 'accessed_at'
    ordering = ['-accessed_at']
    readonly_fields = ['id', 'session_id', 'ip_address', 'user_agent', 'referer', 'accessed_at', 'registered_at']

    list_per_page = 50

    def id_short(self, obj):
        """ID短縮表示"""
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'

    def source_badge(self, obj):
        """流入元をバッジで表示"""
        colors = {
            'flyer': '#FF6B6B',
            'web': '#4ECDC4',
            'social': '#45B7D1',
            'other': '#95A5A6'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.source, '#95A5A6'),
            obj.get_source_display()
        )
    source_badge.short_description = '流入元'

    def session_id_short(self, obj):
        """セッションID短縮表示"""
        return obj.session_id[:20] + '...' if len(obj.session_id) > 20 else obj.session_id
    session_id_short.short_description = 'セッションID'

    def registered_status(self, obj):
        """登録状態の表示"""
        if obj.registered_user:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ 登録済</span>'
            )
        return format_html(
            '<span style="color: gray;">未登録</span>'
        )
    registered_status.short_description = '登録状態'

    def registered_user_link(self, obj):
        """登録ユーザーへのリンク"""
        if obj.registered_user:
            return format_html(
                '<a href="/admin/member_management/user/{}/">{}</a>',
                obj.registered_user.id,
                f"{obj.registered_user.last_name} {obj.registered_user.first_name}"
            )
        return '-'
    registered_user_link.short_description = '登録ユーザー'

    def conversion_time(self, obj):
        """コンバージョンまでの時間"""
        if obj.registered_at and obj.accessed_at:
            delta = obj.registered_at - obj.accessed_at
            hours = delta.total_seconds() / 3600
            if hours < 1:
                minutes = delta.total_seconds() / 60
                return f"{int(minutes)}分"
            elif hours < 24:
                return f"{int(hours)}時間"
            else:
                days = hours / 24
                return f"{int(days)}日"
        return '-'
    conversion_time.short_description = 'CV時間'

    def changelist_view(self, request, extra_context=None):
        """リストビューに統計情報を追加"""
        # 全体統計
        total = CampaignTracking.objects.count()
        registered = CampaignTracking.objects.filter(registered_user__isnull=False).count()
        conversion_rate = (registered / total * 100) if total > 0 else 0

        # 流入元別統計
        source_stats = []
        for source, label in CampaignTracking.Source.choices:
            qs = CampaignTracking.objects.filter(source=source)
            source_total = qs.count()
            source_registered = qs.filter(registered_user__isnull=False).count()
            source_rate = (source_registered / source_total * 100) if source_total > 0 else 0
            source_stats.append({
                'label': label,
                'total': source_total,
                'registered': source_registered,
                'rate': source_rate
            })

        # 直近7日間の統計
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_total = CampaignTracking.objects.filter(accessed_at__gte=seven_days_ago).count()
        recent_registered = CampaignTracking.objects.filter(
            accessed_at__gte=seven_days_ago,
            registered_user__isnull=False
        ).count()
        recent_rate = (recent_registered / recent_total * 100) if recent_total > 0 else 0

        extra_context = extra_context or {}
        extra_context.update({
            'total': total,
            'registered': registered,
            'conversion_rate': conversion_rate,
            'source_stats': source_stats,
            'recent_total': recent_total,
            'recent_registered': recent_registered,
            'recent_rate': recent_rate,
        })

        return super().changelist_view(request, extra_context)

class CustomAdminSite(admin.AdminSite):
    site_header = "Voice Picker AI 管理サイト"
    site_title = "Voice Picker AI Admin"
    index_title = "ダッシュボード"

    @method_decorator(superuser_required)  # ここでデコレーターを適用
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_urls(self):
        """カスタムURLを追加"""
        urls = super().get_urls()
        from voice_picker.admin_views import prompt_analytics_view
        custom_urls = [
            path('prompt-analytics/', self.admin_view(prompt_analytics_view), name='prompt-analytics'),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        """管理サイトのインデックスページをカスタマイズ"""
        extra_context = extra_context or {}

        # 分析ダッシュボードへのリンク情報を追加
        extra_context['custom_links'] = [
            {
                'title': '📊 プロンプト分析',
                'url': '/admin/prompt-analytics/',
                'description': '再生成プロンプトの利用状況を週次で分析'
            },
            {
                'title': '📊 キャンペーン分析',
                'url': '/admin/member_management/campaigntracking/',
                'description': 'チラシ・Web流入の分析'
            },
            {
                'title': '🧪 A/Bテスト結果',
                'url': '/admin/ab_test/abtestsummary/',
                'description': 'A/Bテストの統計情報'
            },
            {
                'title': '💳 サブスクリプション管理',
                'url': '/admin/member_management/subscription/',
                'description': '課金状況の確認'
            },
            {
                'title': '🎯 LP Analytics',
                'url': '/admin/analytics/trackingproject/',
                'description': 'ランディングページの分析とトラッキングID管理'
            }
        ]

        # 簡易統計情報
        from datetime import datetime, timedelta
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        # 直近の登録数
        recent_users = User.objects.filter(created_at__gte=week_ago).count()

        # チラシ流入数
        flyer_access = CampaignTracking.objects.filter(
            source='flyer',
            accessed_at__gte=week_ago
        ).count()
        
        # LP Analytics統計
        lp_page_views = PageView.objects.filter(
            created_at__gte=week_ago
        ).count()
        
        lp_unique_sessions = PageView.objects.filter(
            created_at__gte=week_ago
        ).values('session_id').distinct().count()

        extra_context['quick_stats'] = {
            'recent_users': recent_users,
            'flyer_access': flyer_access,
            'lp_page_views': lp_page_views,
            'lp_unique_sessions': lp_unique_sessions,
        }

        return super().index(request, extra_context)

admin_site = CustomAdminSite(name='custom_admin')
admin_site.register(Organization, OrganizationAdmin)
admin_site.register(User, UserAdmin)
admin_site.register(SubscriptionPlan, SubscriptionPlanAdmin)
admin_site.register(Subscription, SubscriptionAdmin)
admin_site.register(CampaignTracking, CampaignTrackingAdmin)
admin_site.register(Environment, EnvironmentAdmin)
admin_site.register(ScheduledRecording, ScheduledRecordingAdmin)

# LP Analytics モデルを登録
admin_site.register(TrackingProject, TrackingProjectAdmin)
admin_site.register(PageView, PageViewAdmin)
admin_site.register(UserInteraction, UserInteractionAdmin)

# カスタム管理サイトを使用するように設定
admin.site = admin_site
admin.autodiscover()