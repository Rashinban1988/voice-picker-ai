from django.urls import path
from .views import RegisterView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('api/register/', csrf_exempt(RegisterView.as_view()), name='register'),
    path('api/register/verify-email/<uidb64>/', csrf_exempt(RegisterView.verify_email), name='verify_email'),
]
