from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponse
import csv
from .models import ABTestEvent, ABTestSession, ABTestSummary
from member_management.admin import admin_site


# @admin.register(ABTestEvent)  # コメントアウト
class ABTestEventAdmin(admin.ModelAdmin):
    """A/BテストイベントAdmin"""

    list_display = [
        'id', 'variant', 'event', 'session_id_short',
        'user_id_short', 'created_at', 'ip_address'
    ]
    list_filter = ['variant', 'event', 'created_at']
    search_fields = ['session_id', 'user_id', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    # ページあたりの表示件数
    list_per_page = 50

    def session_id_short(self, obj):
        """セッションIDの短縮表示"""
        return obj.session_id[:20] + '...' if len(obj.session_id) > 20 else obj.session_id
    session_id_short.short_description = 'Session ID'

    def user_id_short(self, obj):
        """ユーザーIDの短縮表示"""
        if not obj.user_id:
            return '-'
        return obj.user_id[:20] + '...' if len(obj.user_id) > 20 else obj.user_id
    user_id_short.short_description = 'User ID'

    def export_as_csv(self, request, queryset):
        """選択したイベントをCSVでエクスポート"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="ab_test_events.csv"'
        response.write('\ufeff')  # BOM for Excel

        writer = csv.writer(response)
        writer.writerow(['ID', 'Variant', 'Event', 'Session ID', 'User ID', 'IP Address', 'User Agent', 'Created At'])

        for event in queryset:
            writer.writerow([
                event.id,
                event.variant,
                event.event,
                event.session_id,
                event.user_id or '',
                event.ip_address or '',
                event.user_agent or '',
                event.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response
    export_as_csv.short_description = 'CSVでエクスポート'

    actions = ['export_as_csv']


# @admin.register(ABTestSession)  # コメントアウト
class ABTestSessionAdmin(admin.ModelAdmin):
    """A/BテストセッションAdmin"""

    list_display = [
        'session_id_short', 'variant', 'first_visit',
        'last_activity', 'converted_display', 'conversion_date'
    ]
    list_filter = ['variant', 'converted', 'first_visit']
    search_fields = ['session_id']
    readonly_fields = ['first_visit', 'last_activity']
    date_hierarchy = 'first_visit'
    ordering = ['-first_visit']

    list_per_page = 50

    def session_id_short(self, obj):
        """セッションIDの短縮表示"""
        return obj.session_id[:30] + '...' if len(obj.session_id) > 30 else obj.session_id
    session_id_short.short_description = 'Session ID'

    def converted_display(self, obj):
        """コンバージョン状態の表示"""
        if obj.converted:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Converted</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">Not Converted</span>'
            )
    converted_display.short_description = 'Conversion Status'

    def mark_as_converted(self, request, queryset):
        """選択したセッションをコンバージョン済みにマーク"""
        updated = queryset.update(
            converted=True,
            conversion_date=timezone.now()
        )
        self.message_user(request, f'{updated}件のセッションをコンバージョン済みにしました。')
    mark_as_converted.short_description = 'コンバージョン済みにする'

    def export_sessions_csv(self, request, queryset):
        """セッションデータをCSVエクスポート"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="ab_test_sessions.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Session ID', 'Variant', 'First Visit', 'Last Activity', 'Converted', 'Conversion Date'])

        for session in queryset:
            writer.writerow([
                session.session_id,
                session.variant,
                session.first_visit.strftime('%Y-%m-%d %H:%M:%S'),
                session.last_activity.strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if session.converted else 'No',
                session.conversion_date.strftime('%Y-%m-%d %H:%M:%S') if session.conversion_date else ''
            ])

        return response
    export_sessions_csv.short_description = 'CSVでエクスポート'

    actions = ['mark_as_converted', 'export_sessions_csv']


# @admin.register(ABTestSummary)  # コメントアウト
class ABTestSummaryAdmin(admin.ModelAdmin):
    """A/BテストサマリーAdmin"""

    list_display = [
        'date', 'variant', 'page_views', 'register_clicks',
        'conversions', 'conversion_rate_display', 'unique_sessions'
    ]
    list_filter = ['variant', 'date']
    search_fields = ['date']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    ordering = ['-date', 'variant']

    list_per_page = 50

    def conversion_rate_display(self, obj):
        """コンバージョン率の表示"""
        rate = obj.conversion_rate * 100
        color = 'green' if rate >= 5 else 'orange' if rate >= 2 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color, rate
        )
    conversion_rate_display.short_description = 'Conversion Rate'

    # カスタムアクション
    def generate_summary_for_date_range(self, request, queryset):
        """選択した期間のサマリーを再生成"""
        from django.contrib import messages
        from django.core.management import call_command

        dates = queryset.values_list('date', flat=True).distinct()
        for date in dates:
            try:
                call_command('generate_ab_test_summary', date=date.strftime('%Y-%m-%d'))
                messages.success(request, f'{date}のサマリーを再生成しました。')
            except Exception as e:
                messages.error(request, f'{date}のサマリー生成でエラー: {str(e)}')
    generate_summary_for_date_range.short_description = '選択した日付のサマリーを再生成'

    actions = ['generate_summary_for_date_range']

    # 統計情報を表示するカスタムビュー
    def changelist_view(self, request, extra_context=None):
        # 全体の統計を計算
        total_stats = ABTestSummary.objects.aggregate(
            total_page_views=Sum('page_views'),
            total_register_clicks=Sum('register_clicks'),
            total_login_clicks=Sum('login_clicks'),
            total_conversions=Sum('conversions'),
            total_sessions=Sum('unique_sessions')
        )

        # バリアント別の統計を計算
        stats = {}
        for variant in ['A', 'B']:
            variant_queryset = ABTestSummary.objects.filter(variant=variant)
            variant_stats = variant_queryset.aggregate(
                total_page_views=Sum('page_views'),
                total_register_clicks=Sum('register_clicks'),
                total_login_clicks=Sum('login_clicks'),
                total_conversions=Sum('conversions'),
                total_sessions=Sum('unique_sessions'),
                avg_conversion_rate=Avg('conversion_rate')
            )

            # コンバージョン率を計算
            if variant_stats['total_sessions'] and variant_stats['total_sessions'] > 0:
                variant_stats['conversion_rate'] = (variant_stats['total_conversions'] / variant_stats['total_sessions']) * 100
            else:
                variant_stats['conversion_rate'] = 0

            stats[f'variant_{variant}'] = variant_stats

        # 直近7日間の統計
        seven_days_ago = timezone.now().date() - timedelta(days=7)
        recent_stats = ABTestSummary.objects.filter(date__gte=seven_days_ago).aggregate(
            recent_page_views=Sum('page_views'),
            recent_conversions=Sum('conversions'),
            recent_sessions=Sum('unique_sessions')
        )

        extra_context = extra_context or {}
        extra_context.update({
            'total_stats': total_stats,
            'stats': stats,
            'recent_stats': recent_stats,
        })

        return super().changelist_view(request, extra_context)


# カスタム管理サイトにABテストモデルを登録
admin_site.register(ABTestEvent, ABTestEventAdmin)
admin_site.register(ABTestSession, ABTestSessionAdmin)
admin_site.register(ABTestSummary, ABTestSummaryAdmin)