from rest_framework import serializers
from .models import UploadedFile, Transcription, Environment
from member_management.models import Organization
import os

class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Environment
        fields = ['id', 'code', 'value', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class UploadedFileSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False)
    file = serializers.FileField()

    class Meta:
        model = UploadedFile
        fields = '__all__'
        read_only_fields = ['organization', 'created_at', 'updated_at', 'deleted_at', 'exist']

    def get_file(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None

class TranscriptionSerializer(serializers.ModelSerializer):
    uploaded_file = serializers.PrimaryKeyRelatedField(queryset=UploadedFile.objects.all())

    class Meta:
        model = Transcription
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'deleted_at', 'exist']