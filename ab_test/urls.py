from django.urls import path
from .views import (
    ABTestTrackView,
    ABTestStatsView,
    ABTestDailyStatsView,
    ABTestEventsView
)

app_name = 'ab_test'

urlpatterns = [
    # A/Bテストイベントトラッキング
    path('track/', ABTestTrackView.as_view(), name='track'),
    
    # 統計情報取得
    path('stats/', ABTestStatsView.as_view(), name='stats'),
    path('stats/daily/', ABTestDailyStatsView.as_view(), name='daily_stats'),
    
    # イベント一覧取得（管理用）
    path('events/', ABTestEventsView.as_view(), name='events'),
]