from rest_framework import serializers
from .models import UploadedFile, Transcription

class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = '__all__'

class TranscriptionSerializer(serializers.ModelSerializer):
    uploaded_file = serializers.PrimaryKeyRelatedField(queryset=UploadedFile.objects.all())

    class Meta:
        model = Transcription
        fields = '__all__'