from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from .models import UploadedFile, Transcription, PromptHistory

class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization_id', 'file', 'duration', 'status', 'summarization', 'issue', 'solution', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['status', 'organization_id', 'created_at', 'updated_at', 'deleted_at']
    search_fields = ['file', 'organization_id', 'summarization', 'issue', 'solution']

class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'uploaded_file', 'start_time', 'text', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['text']

class PromptHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'organization', 'uploaded_file', 'prompt_type',
        'instruction_category', 'year', 'week_of_year', 'created_at'
    ]
    list_filter = [
        'prompt_type', 'instruction_category', 'year', 'week_of_year',
        'organization', 'created_at'
    ]
    search_fields = ['custom_instruction', 'generated_result', 'instruction_keywords']
    readonly_fields = ['week_of_year', 'year', 'instruction_keywords', 'instruction_category']

    change_list_template = 'admin/voice_picker/prompthistory/change_list.html'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization', 'uploaded_file')

    def changelist_view(self, request, extra_context=None):
        # 分析ダッシュボードへのリンクを追加
        extra_context = extra_context or {}
        extra_context['show_analytics_link'] = True
        return super().changelist_view(request, extra_context=extra_context)

# 既存の登録を標準管理サイトに追加
admin.site.register(UploadedFile, UploadedFileAdmin)
admin.site.register(Transcription, TranscriptionAdmin)
admin.site.register(PromptHistory, PromptHistoryAdmin)