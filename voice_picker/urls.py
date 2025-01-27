from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from .views import UploadedFileViewSet, TranscriptionViewSet, TranscribeView

urlpatterns = [
    # UploadedFileの一覧を取得と新規作成を行うためのパス
    path('api/uploaded-files/', csrf_exempt(UploadedFileViewSet.as_view({
        'get': 'list',  # GETリクエストでorganization_idをボディに含めることが可能
        'post': 'create'
    })), name='uploaded-files-list'),

    # UploadedFileの詳細を取得するためのパス
    path('api/uploaded-files/<int:pk>/', csrf_exempt(UploadedFileViewSet.as_view({
        'get': 'retrieve'
    })), name='uploaded-file-detail'),

    # Transcriptionの一覧を取得と新規作成を行うためのパス
    path('api/transcriptions/', csrf_exempt(TranscriptionViewSet.as_view({
        'get': 'list',
        'post': 'create'
    })), name='transcriptions-list'),

    # UploadedFileのIDに紐づいたTranscriptionの一覧を取得するための新しいパス
    path('api/transcriptions/uploaded-file/<uuid:uploadedfile_id>/', csrf_exempt(TranscriptionViewSet.as_view({
        'get': 'list'
    })), name='transcriptions-by-uploadedfile'),

    # 新しいパス
    path('api/transcribe/', csrf_exempt(TranscribeView.as_view()), name='transcribe')
]
