from django.urls import path
from rest_framework import routers
from .views import UploadedFileViewSet
from django.views.decorators.csrf import csrf_exempt

router = routers.DefaultRouter()

urlpatterns = [
    path('upload-files/total-duration/', csrf_exempt(UploadedFileViewSet.as_view({'post': 'total_duration'})), name='total_duration'),
    path('upload-files/audio/<uuid:pk>/', csrf_exempt(UploadedFileViewSet.as_view({'get': 'audio'})), name='audio'),
]

urlpatterns += router.urls
