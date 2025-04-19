from django.urls import path
from rest_framework import routers
from .views import UserViewSet, OrganizationViewSet
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView
from django.views.decorators.csrf import csrf_exempt
from .views import RegisterView, UserViewSet, EmailVerificationView

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'organizations', OrganizationViewSet, basename='organizations')

urlpatterns = [
    path('register/', csrf_exempt(RegisterView.as_view()), name='register'),
    path('register/verify-email/<uidb64>/', csrf_exempt(EmailVerificationView.as_view()), name='verify_email'),
    path('token/', csrf_exempt(CustomTokenObtainPairView.as_view()), name='token_obtain_pair'),
    path('token/refresh/', csrf_exempt(TokenRefreshView.as_view()), name='token_refresh'),
    path('users/me/', csrf_exempt(UserViewSet.as_view({'get': 'me'})), name='users_me'),
    path('users/password-change/', csrf_exempt(UserViewSet.as_view({'post': 'password_change'})), name='password_change'),
]

urlpatterns += router.urls
