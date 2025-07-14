from django.urls import path, re_path
from rest_framework import routers
from .views import UploadedFileViewSet, TranscriptionViewSet, TranscriptionSaveViewSet, EnvironmentViewSet
from .hls_views import serve_hls_content
from django.views.decorators.csrf import csrf_exempt

router = routers.DefaultRouter()

urlpatterns = [
    path('environments/<str:code>/', csrf_exempt(EnvironmentViewSet.as_view({'post': 'update'})), name='environment-detail'),
    path('upload-files/total-duration/', csrf_exempt(UploadedFileViewSet.as_view({'post': 'total_duration'})), name='total_duration'),
    path('upload-files/audio/<uuid:pk>/', csrf_exempt(UploadedFileViewSet.as_view({'get': 'audio'})), name='audio'),
    path('upload-files/<uuid:pk>/stream-url/', csrf_exempt(UploadedFileViewSet.as_view({'post': 'stream_url'})), name='stream-url'),
    path('upload-files/stream/<uuid:pk>/', csrf_exempt(UploadedFileViewSet.as_view({'get': 'stream'})), name='stream'),
    path('upload-files/<uuid:pk>/hls-info/', csrf_exempt(UploadedFileViewSet.as_view({'get': 'hls_info'})), name='hls-info'),
    re_path(r'^hls-stream/(?P<file_id>[0-9a-f-]+)/(?P<filename>.+)$', serve_hls_content, name='hls-stream'),
    path('transcriptions/save-transcriptions/', csrf_exempt(TranscriptionSaveViewSet.as_view({'post': 'save_transcriptions'})), name='save_transcriptions'),
]

urlpatterns += router.urls
