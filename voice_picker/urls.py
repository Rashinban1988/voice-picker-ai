from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from .views import (
    UploadedFileViewSet, TranscriptionViewSet, TranscribeView, RegenerateAnalysisViewSet,
    validate_zoom_meeting_url, start_zoom_recording, stop_zoom_recording,
    get_zoom_recording_status, get_active_zoom_recordings,
    get_meeting_details, schedule_zoom_recording, get_scheduled_recordings,
    cancel_scheduled_recording, get_scheduled_recording_status, recording_completed,
    create_uploaded_file_record
)

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
    path('api/transcribe/', csrf_exempt(TranscribeView.as_view()), name='transcribe'),

    path('api/regenerate/summary/', csrf_exempt(RegenerateAnalysisViewSet.as_view({
        'post': 'regenerate_summary'
    })), name='regenerate-summary'),
    
    path('api/regenerate/issues/', csrf_exempt(RegenerateAnalysisViewSet.as_view({
        'post': 'regenerate_issues'
    })), name='regenerate-issues'),
    
    path('api/regenerate/solutions/', csrf_exempt(RegenerateAnalysisViewSet.as_view({
        'post': 'regenerate_solutions'
    })), name='regenerate-solutions'),
    
    path('api/regenerate/prompt-analytics/', csrf_exempt(RegenerateAnalysisViewSet.as_view({
        'get': 'get_prompt_analytics'
    })), name='prompt-analytics'),
    
    # Zoom会議録画用API
    path('api/zoom/validate-url/', csrf_exempt(validate_zoom_meeting_url), name='validate-zoom-url'),
    path('api/zoom/start-recording/', csrf_exempt(start_zoom_recording), name='start-zoom-recording'),
    path('api/zoom/stop-recording/', csrf_exempt(stop_zoom_recording), name='stop-zoom-recording'),
    path('api/zoom/recording-status/<uuid:uploaded_file_id>/', csrf_exempt(get_zoom_recording_status), name='zoom-recording-status'),
    path('api/zoom/active-recordings/', csrf_exempt(get_active_zoom_recordings), name='active-zoom-recordings'),
    
    # 予約録画用API
    path('api/zoom/meeting-details/', csrf_exempt(get_meeting_details), name='get-meeting-details'),
    path('api/zoom/schedule-recording/', csrf_exempt(schedule_zoom_recording), name='schedule-zoom-recording'),
    path('api/zoom/scheduled-recordings/', csrf_exempt(get_scheduled_recordings), name='get-scheduled-recordings'),
    path('api/zoom/cancel-recording/', csrf_exempt(cancel_scheduled_recording), name='cancel-scheduled-recording'),
    path('api/zoom/scheduled-recording-status/<uuid:recording_id>/', csrf_exempt(get_scheduled_recording_status), name='scheduled-recording-status'),
    path('api/zoom/recording-completed/', csrf_exempt(recording_completed), name='recording-completed'),
    path('api/zoom/create-uploaded-file/', csrf_exempt(create_uploaded_file_record), name='create-uploaded-file'),
]
