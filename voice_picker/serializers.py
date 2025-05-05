from rest_framework import serializers
from .models import UploadedFile, Transcription
from member_management.models import Organization

class UploadedFileSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False)

    class Meta:
        model = UploadedFile
        fields = '__all__'
        read_only_fields = ['organization', 'created_at', 'updated_at', 'deleted_at', 'exist']

class TranscriptionSerializer(serializers.ModelSerializer):
    uploaded_file = serializers.PrimaryKeyRelatedField(queryset=UploadedFile.objects.all())

    class Meta:
        model = Transcription
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'deleted_at', 'exist']