from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('api/register/', csrf_exempt(RegisterView.as_view()), name='register'),
    path('api/register/verify-email/<uidb64>/', csrf_exempt(RegisterView.verify_email), name='verify_email'),
    path('api/token/', csrf_exempt(TokenObtainPairView.as_view()), name='token_obtain_pair'),  # トークン取得
    path('api/token/refresh/', csrf_exempt(TokenRefreshView.as_view()), name='token_refresh'),       # トークンリフレッシュ
]
