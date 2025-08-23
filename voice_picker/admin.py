from django.contrib import admin
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization', 'uploaded_file')

admin.site.register(UploadedFile, UploadedFileAdmin)
admin.site.register(Transcription, TranscriptionAdmin)
admin.site.register(PromptHistory, PromptHistoryAdmin)