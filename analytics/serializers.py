from rest_framework import serializers
from .models import TrackingProject, PageView, UserInteraction, HeatmapData, ScrollDepth


class PageViewSerializer(serializers.ModelSerializer):
    tracking_id = serializers.CharField(write_only=True)

    class Meta:
        model = PageView
        fields = [
            'tracking_id', 'session_id', 'page_url', 'page_title',
            'referrer', 'user_agent', 'ip_address', 'screen_width',
            'screen_height'
        ]

    def create(self, validated_data):
        tracking_id = validated_data.pop('tracking_id')

        # デバッグ：データベース設定と全プロジェクトを確認
        from django.db import connection
        print(f"DEBUG - Database: {connection.settings_dict['NAME']}")
        all_projects = TrackingProject.objects.all()
        print(f"DEBUG - Total projects in DB: {all_projects.count()}")
        for p in all_projects:
            print(f"DEBUG - Project: {p.tracking_id} (active: {p.is_active})")

        # tracking_idでプロジェクトを検索
        projects = TrackingProject.objects.filter(tracking_id=tracking_id)
        print(f"DEBUG - Found {projects.count()} projects for tracking_id: {tracking_id}")

        if not projects.exists():
            # tracking_idが存在しない
            raise serializers.ValidationError({
                'tracking_id': f'No project found with tracking_id: {tracking_id}'
            })

        project = projects.filter(is_active=True).first()
        if not project:
            # プロジェクトは存在するが非アクティブ
            raise serializers.ValidationError({
                'tracking_id': f'Project {tracking_id} is not active'
            })

        validated_data['project'] = project
        return super().create(validated_data)


class UserInteractionSerializer(serializers.ModelSerializer):
    page_view_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = UserInteraction
        fields = [
            'page_view_id', 'event_type', 'x_coordinate', 'y_coordinate',
            'scroll_percentage', 'element_selector', 'element_text',
            'viewport_width', 'viewport_height', 'timestamp'
        ]

    def create(self, validated_data):
        page_view_id = validated_data.pop('page_view_id')

        try:
            page_view = PageView.objects.get(id=page_view_id)
        except PageView.DoesNotExist:
            raise serializers.ValidationError({'page_view_id': 'Invalid page view ID'})

        validated_data['page_view'] = page_view
        return super().create(validated_data)


class BatchInteractionSerializer(serializers.Serializer):
    events = UserInteractionSerializer(many=True)

    def create(self, validated_data):
        events_data = validated_data['events']
        interactions = []

        for event_data in events_data:
            serializer = UserInteractionSerializer(data=event_data)
            if serializer.is_valid():
                interactions.append(serializer.save())

        return interactions


class TrackingProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingProject
        fields = ['id', 'name', 'tracking_id', 'domain', 'is_active', 'created_at']
        read_only_fields = ['id', 'tracking_id', 'created_at']