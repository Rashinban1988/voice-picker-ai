from django.urls import include, path

urlpatterns = [
    path('', include('member_management.api_urls')),
    path('', include('voice_picker.api_urls')),
    path('', include('ab_test.api_urls')),
]
