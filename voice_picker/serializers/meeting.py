from rest_framework import serializers
from voice_picker.models.meeting import Meeting

class MeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['id', 'meeting_url', 'meeting_platform', 'scheduled_time', 'duration_minutes', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']
