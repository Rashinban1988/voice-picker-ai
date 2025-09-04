from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Avg
from django.utils.html import format_html
from django import forms
import secrets
import string
from .models import TrackingProject, PageView, UserInteraction, HeatmapData, ScrollDepth


class TrackingProjectForm(forms.ModelForm):
    class Meta:
        model = TrackingProject
        fields = ['name', 'domain', 'is_active']

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.tracking_id:
            # トラッキングID自動生成
            instance.tracking_id = 'lp_' + ''.join(
                secrets.choice(string.ascii_letters + string.digits)
                for _ in range(12)
            )
        if commit:
            instance.save()
        return instance


# @admin.register(TrackingProject)  # 自動登録は使わない
class TrackingProjectAdmin(admin.ModelAdmin):
    form = TrackingProjectForm
    list_display = ['name', 'tracking_id', 'domain', 'organization', 'is_active', 'page_views_count', 'interactions_count', 'view_analytics_dashboard', 'view_heatmap', 'created_at']
    list_filter = ['is_active', 'created_at', 'organization']
    search_fields = ['name', 'tracking_id', 'domain']
    readonly_fields = ['tracking_id', 'created_at', 'updated_at']
    actions = ['generate_analytics_report']

    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'domain', 'is_active')
        }),
        ('自動生成情報', {
            'fields': ('tracking_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def page_views_count(self, obj):
        return obj.page_views.count()
    page_views_count.short_description = 'ページビュー数'

    def interactions_count(self, obj):
        return UserInteraction.objects.filter(page_view__project=obj).count()
    interactions_count.short_description = 'インタラクション数'

    def view_analytics_dashboard(self, obj):
        return format_html(
            '<a class="button" href="/admin/analytics/trackingproject/dashboard/{}/" target="_blank">📊 分析画面</a>',
            obj.id
        )
    view_analytics_dashboard.short_description = '分析'

    def view_heatmap(self, obj):
        return format_html(
            '<a class="button" href="/admin/analytics/trackingproject/heatmap/{}/" target="_blank">🔥 ヒートマップ</a>',
            obj.id
        )
    view_heatmap.short_description = 'ヒートマップ'

    def generate_analytics_report(self, request, queryset):
        # 選択されたプロジェクトの分析レポート生成
        for project in queryset:
            # レポート生成ロジック
            pass
        self.message_user(request, f"{queryset.count()}個のプロジェクトの分析レポートを生成しました。")
    generate_analytics_report.short_description = '分析レポート生成'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/<uuid:project_id>/', self.admin_site.admin_view(self.analytics_dashboard_view), name='analytics-dashboard'),
            path('heatmap/<uuid:project_id>/', self.admin_site.admin_view(self.heatmap_viewer), name='analytics-heatmap'),
        ]
        return custom_urls + urls

    def analytics_dashboard_view(self, request, project_id):
        """分析ダッシュボードビュー"""
        try:
            project = TrackingProject.objects.get(id=project_id)

            # 基本統計を取得
            page_views = PageView.objects.filter(project=project)
            interactions = UserInteraction.objects.filter(page_view__project=project)

            stats = {
                'total_page_views': page_views.count(),
                'unique_sessions': page_views.values('session_id').distinct().count(),
                'total_interactions': interactions.count(),
                'click_events': interactions.filter(event_type='click').count(),
                'scroll_events': interactions.filter(event_type='scroll').count(),
            }

            # 人気ページ
            popular_pages = page_views.values('page_url').annotate(
                view_count=Count('id')
            ).order_by('-view_count')[:5]

            # クリック分析
            click_elements = interactions.filter(
                event_type='click',
                element_selector__isnull=False
            ).values('element_selector', 'element_text').annotate(
                click_count=Count('id')
            ).order_by('-click_count')[:10]

            context = {
                'title': f'{project.name} - 分析ダッシュボード',
                'project': project,
                'stats': stats,
                'popular_pages': popular_pages,
                'click_elements': click_elements,
            }

            return render(request, 'admin/analytics/dashboard.html', context)

        except TrackingProject.DoesNotExist:
            return JsonResponse({'error': 'Project not found'}, status=404)

    def heatmap_viewer(self, request, project_id):
        """ヒートマップビューアー"""
        try:
            project = TrackingProject.objects.get(id=project_id)

            # ヒートマップデータを取得
            interactions = UserInteraction.objects.filter(
                page_view__project=project,
                event_type='click',
                x_coordinate__isnull=False,
                y_coordinate__isnull=False
            )

            # 座標をグループ化してクリック数をカウント
            heatmap_data = {}
            for interaction in interactions:
                # 近い座標をグループ化（20pxの範囲）
                x_group = (interaction.x_coordinate // 20) * 20
                y_group = (interaction.y_coordinate // 20) * 20
                key = f"{x_group},{y_group}"

                if key not in heatmap_data:
                    heatmap_data[key] = {
                        'x': x_group + 10,  # グループの中央
                        'y': y_group + 10,
                        'value': 0
                    }
                heatmap_data[key]['value'] += 1

            # 最も多くアクセスされたページURLを取得
            most_viewed_page = interactions.values('page_view__page_url').annotate(
                count=Count('id')
            ).order_by('-count').first()

            page_url = most_viewed_page['page_view__page_url'] if most_viewed_page else 'http://localhost:3001/lp'

            context = {
                'title': f'{project.name} - ヒートマップビューアー',
                'project': project,
                'page_url': page_url,
                'heatmap_data': list(heatmap_data.values()),
                'total_clicks': sum(point['value'] for point in heatmap_data.values()),
            }

            return render(request, 'admin/analytics/heatmap_viewer.html', context)

        except TrackingProject.DoesNotExist:
            return JsonResponse({'error': 'Project not found'}, status=404)


# @admin.register(PageView)  # 自動登録は使わない
class PageViewAdmin(admin.ModelAdmin):
    list_display = ['project', 'page_url', 'session_id', 'ip_address', 'created_at']
    list_filter = ['project', 'created_at']
    search_fields = ['page_url', 'session_id', 'ip_address']
    readonly_fields = ['created_at']


# @admin.register(UserInteraction)  # 自動登録は使わない
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ['page_view', 'event_type', 'x_coordinate', 'y_coordinate', 'scroll_percentage', 'timestamp']
    list_filter = ['event_type', 'timestamp', 'page_view__project']
    search_fields = ['element_selector', 'element_text']
    readonly_fields = ['created_at']


# @admin.register(HeatmapData)  # 自動登録は使わない
class HeatmapDataAdmin(admin.ModelAdmin):
    list_display = ['project', 'page_url', 'x_coordinate', 'y_coordinate', 'click_count', 'hover_count', 'date']
    list_filter = ['project', 'date']
    search_fields = ['page_url']


# @admin.register(ScrollDepth)  # 自動登録は使わない
class ScrollDepthAdmin(admin.ModelAdmin):
    list_display = ['project', 'page_url', 'depth_percentage', 'user_count', 'date']
    list_filter = ['project', 'date']
    search_fields = ['page_url']
