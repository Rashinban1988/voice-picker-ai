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
    # 再生成回数関連の追加フィールド
    remaining_summarization_generations = serializers.SerializerMethodField()
    remaining_issue_generations = serializers.SerializerMethodField()
    remaining_solution_generations = serializers.SerializerMethodField()
    max_generations = serializers.SerializerMethodField()

    class Meta:
        model = UploadedFile
        fields = '__all__'
        read_only_fields = ['organization', 'created_at', 'updated_at', 'deleted_at', 'exist']

    def get_file(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None

    def get_remaining_summarization_generations(self, obj):
        """要約の残り再生成回数を計算"""
        return max(0, 5 - obj.summarization_generation_count)

    def get_remaining_issue_generations(self, obj):
        """課題の残り再生成回数を計算"""
        return max(0, 5 - obj.issue_generation_count)

    def get_remaining_solution_generations(self, obj):
        """取り組み案の残り再生成回数を計算"""
        return max(0, 5 - obj.solution_generation_count)

    def get_max_generations(self, obj):
        """最大再生成回数を返す"""
        return 5

class TranscriptionSerializer(serializers.ModelSerializer):
    uploaded_file = serializers.PrimaryKeyRelatedField(queryset=UploadedFile.objects.all())

    class Meta:
        model = Transcription
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'deleted_at', 'exist']