from rest_framework import serializers
from voice_picker.models.meeting import Meeting
from voice_picker.utils.meeting_url_parser import extract_meeting_info

class MeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['id', 'meeting_url', 'meeting_platform', 'scheduled_time', 'duration_minutes', 'status', 'recorded_file_path', 'uploaded_file', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'recorded_file_path', 'uploaded_file', 'created_at', 'updated_at', 'meeting_platform', 'scheduled_time']

    def create(self, validated_data):
        url = validated_data['meeting_url']
        meeting_info = extract_meeting_info(url)
        
        validated_data['meeting_platform'] = meeting_info['platform']
        validated_data['scheduled_time'] = meeting_info['scheduled_time']
        validated_data['duration_minutes'] = meeting_info['duration_minutes']
        
        return super().create(validated_data)
