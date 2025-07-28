from django.urls import path, include

urlpatterns = [
    path('ab-test/', include('ab_test.urls')),
]