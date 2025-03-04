from django.urls import path
from rest_framework import routers
from .views import UserViewSet, OrganizationViewSet
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView
from django.views.decorators.csrf import csrf_exempt

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'organizations', OrganizationViewSet, basename='organizations')

urlpatterns = [
    path('token/', csrf_exempt(CustomTokenObtainPairView.as_view()), name='token_obtain_pair'),  # トークン取得
    path('token/refresh/', csrf_exempt(TokenRefreshView.as_view()), name='token_refresh'),       # トークンリフレッシュ
]

urlpatterns += router.urls

