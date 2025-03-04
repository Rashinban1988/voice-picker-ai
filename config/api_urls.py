from django.urls import include, path

urlpatterns = [
    path('', include('member_management.api_urls')),
]
