from django.urls import path
from .views_flyer import CampaignStatsView

urlpatterns = [
    path('campaign-stats/', CampaignStatsView.as_view(), name='campaign_stats'),
]
