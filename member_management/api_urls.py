from django.urls import path
from rest_framework import routers
from .views import UserViewSet, OrganizationViewSet
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView
from django.views.decorators.csrf import csrf_exempt
from .views import (
    RegisterView, UserViewSet, EmailVerificationView,
    SubscriptionPlanViewSet, SubscriptionViewSet, StripeWebhookView
)

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'organizations', OrganizationViewSet, basename='organizations')
router.register(r'subscription-plans', SubscriptionPlanViewSet, basename='subscription-plans')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscriptions')

urlpatterns = [
    path('register/', csrf_exempt(RegisterView.as_view()), name='register'),
    path('register/verify-email/<uidb64>/', csrf_exempt(EmailVerificationView.as_view()), name='verify_email'),
    path('token/', csrf_exempt(CustomTokenObtainPairView.as_view()), name='token_obtain_pair'),
    path('token/refresh/', csrf_exempt(TokenRefreshView.as_view()), name='token_refresh'),
    path('users/me/', csrf_exempt(UserViewSet.as_view({'get': 'me'})), name='users_me'),
    path('users/password-change/', csrf_exempt(UserViewSet.as_view({'post': 'password_change'})), name='password_change'),
    
    path('subscriptions/create-checkout-session/', 
         csrf_exempt(SubscriptionViewSet.as_view({'post': 'create_checkout_session'})), 
         name='create_checkout_session'),
    path('subscriptions/manage-portal/', 
         csrf_exempt(SubscriptionViewSet.as_view({'post': 'manage_portal'})), 
         name='manage_portal'),
    path('webhook/stripe/', csrf_exempt(StripeWebhookView.as_view()), name='stripe_webhook'),
]

urlpatterns += router.urls
