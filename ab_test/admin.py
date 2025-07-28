from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import ABTestEvent, ABTestSession, ABTestSummary


@admin.register(ABTestEvent)
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


@admin.register(ABTestSession)
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


@admin.register(ABTestSummary)
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
    
    # 統計情報を表示するカスタムビュー
    def changelist_view(self, request, extra_context=None):
        # バリアント別の統計を計算
        stats = {}
        for variant in ['A', 'B']:
            variant_stats = ABTestSummary.objects.filter(variant=variant).aggregate(
                total_page_views=Count('page_views'),
                total_conversions=Count('conversions'),
            )
            stats[f'variant_{variant}'] = variant_stats
        
        extra_context = extra_context or {}
        extra_context['stats'] = stats
        
        return super().changelist_view(request, extra_context)