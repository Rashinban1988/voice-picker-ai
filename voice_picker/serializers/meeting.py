from rest_framework import serializers
from voice_picker.models.meeting import Meeting

class MeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['id', 'meeting_url', 'meeting_platform', 'scheduled_time', 'duration_minutes', 'status', 'recorded_file_path', 'uploaded_file', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'recorded_file_path', 'uploaded_file', 'created_at', 'updated_at']
