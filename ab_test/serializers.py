from rest_framework import serializers
from .models import ABTestEvent, ABTestSession, ABTestSummary


class ABTestEventSerializer(serializers.ModelSerializer):
    """A/Bテストイベント用シリアライザー"""
    
    class Meta:
        model = ABTestEvent
        fields = [
            'variant', 'event', 'timestamp', 'session_id', 
            'user_id', 'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['ip_address', 'user_agent', 'created_at']
    
    def validate_variant(self, value):
        """バリアントの検証"""
        if value not in ['A', 'B']:
            raise serializers.ValidationError('Variant must be A or B')
        return value
    
    def validate_event(self, value):
        """イベントタイプの検証"""
        valid_events = ['page_view', 'register_click', 'login_click', 'conversion']
        if value not in valid_events:
            raise serializers.ValidationError(f'Event must be one of: {valid_events}')
        return value


class ABTestTrackRequestSerializer(serializers.Serializer):
    """フロントエンドからのトラッキングリクエスト用シリアライザー"""
    
    variant = serializers.ChoiceField(choices=['A', 'B'])
    event = serializers.ChoiceField(
        choices=['page_view', 'register_click', 'login_click', 'conversion']
    )
    timestamp = serializers.IntegerField()
    sessionId = serializers.CharField(max_length=100, source='session_id')
    userId = serializers.CharField(max_length=100, required=False, allow_blank=True, source='user_id')


class ABTestSessionSerializer(serializers.ModelSerializer):
    """A/Bテストセッション用シリアライザー"""
    
    class Meta:
        model = ABTestSession
        fields = [
            'session_id', 'variant', 'first_visit', 'last_activity',
            'converted', 'conversion_date'
        ]


class ABTestSummarySerializer(serializers.ModelSerializer):
    """A/Bテストサマリー用シリアライザー"""
    
    class Meta:
        model = ABTestSummary
        fields = [
            'date', 'variant', 'page_views', 'register_clicks', 
            'login_clicks', 'conversions', 'unique_sessions', 
            'conversion_rate'
        ]


class ABTestStatsResponseSerializer(serializers.Serializer):
    """統計レスポンス用シリアライザー"""
    
    variantA = serializers.DictField()
    variantB = serializers.DictField()
    period = serializers.DictField()
    
    
class ABTestVariantStatsSerializer(serializers.Serializer):
    """バリアント別統計用シリアライザー"""
    
    pageViews = serializers.IntegerField()
    registerClicks = serializers.IntegerField()
    loginClicks = serializers.IntegerField()
    conversions = serializers.IntegerField()
    uniqueSessions = serializers.IntegerField()
    conversionRate = serializers.FloatField()
    clickThroughRate = serializers.FloatField()


class ABTestPeriodSerializer(serializers.Serializer):
    """期間情報用シリアライザー"""
    
    startDate = serializers.DateField()
    endDate = serializers.DateField()