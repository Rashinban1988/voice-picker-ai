from django.contrib import admin
from .models import UploadedFile, Transcription

class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization_id', 'file', 'summarization','issue','solution','status', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['status', 'organization_id', 'created_at', 'updated_at', 'deleted_at']
    search_fields = ['file', 'organization_id', 'summarization', 'issue', 'solution']

class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'uploaded_file', 'start_time', 'text', 'created_at', 'updated_at', 'deleted_at']
    list_filter = ['created_at', 'updated_at', 'deleted_at']
    search_fields = ['text']

admin.site.register(UploadedFile, UploadedFileAdmin)
admin.site.register(Transcription, TranscriptionAdmin)