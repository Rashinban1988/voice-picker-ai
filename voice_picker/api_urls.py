from django.urls import path
from rest_framework import routers
from .views import UploadedFileViewSet, TranscriptionViewSet, TranscriptionSaveViewSet, EnvironmentViewSet
from django.views.decorators.csrf import csrf_exempt

router = routers.DefaultRouter()

urlpatterns = [
    path('environments/<str:code>/', csrf_exempt(EnvironmentViewSet.as_view({'post': 'update'})), name='environment-detail'),
    path('upload-files/total-duration/', csrf_exempt(UploadedFileViewSet.as_view({'post': 'total_duration'})), name='total_duration'),
    path('upload-files/audio/<uuid:pk>/', csrf_exempt(UploadedFileViewSet.as_view({'get': 'audio'})), name='audio'),
    path('transcriptions/save-transcriptions/', csrf_exempt(TranscriptionSaveViewSet.as_view({'post': 'save_transcriptions'})), name='save_transcriptions'),
]

urlpatterns += router.urls
