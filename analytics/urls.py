from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TrackingProjectViewSet,
    PageViewCreateAPIView,
    InteractionCreateAPIView,
    AnalyticsDashboardViewSet,
    test_page_view,
    cdn_sdk_serve
)

router = DefaultRouter()
router.register(r'projects', TrackingProjectViewSet, basename='tracking-project')
router.register(r'dashboard', AnalyticsDashboardViewSet, basename='analytics-dashboard')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/page-view/', PageViewCreateAPIView.as_view(), name='page-view-create'),
    path('api/interactions/', InteractionCreateAPIView.as_view(), name='interaction-create'),
    path('test/<str:tracking_id>/', test_page_view, name='test-page'),

    # CDN SDK distribution
    path('sdk/lp-analytics.js', cdn_sdk_serve, name='cdn-sdk'),
]