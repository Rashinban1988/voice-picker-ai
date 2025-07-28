from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
import logging

from .models import ABTestEvent, ABTestSession, ABTestSummary
from .serializers import (
    ABTestTrackRequestSerializer, 
    ABTestEventSerializer,
    ABTestStatsResponseSerializer,
    ABTestVariantStatsSerializer
)

logger = logging.getLogger(__name__)


class ABTestTrackView(APIView):
    """A/Bテストイベントトラッキング API"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        """A/Bテストイベントを記録"""
        try:
            serializer = ABTestTrackRequestSerializer(data=request.data)
            
            if not serializer.is_valid():
                return Response(
                    {'error': 'Invalid data', 'details': serializer.errors}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            validated_data = serializer.validated_data
            
            # IPアドレスとUser-Agentを取得
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            with transaction.atomic():
                # イベント記録
                event = ABTestEvent.objects.create(
                    variant=validated_data['variant'],
                    event=validated_data['event'],
                    timestamp=validated_data['timestamp'],
                    session_id=validated_data['session_id'],
                    user_id=validated_data.get('user_id'),
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # セッション情報の更新または作成
                session, created = ABTestSession.objects.get_or_create(
                    session_id=validated_data['session_id'],
                    defaults={
                        'variant': validated_data['variant'],
                        'first_visit': timezone.now(),
                    }
                )
                
                # コンバージョンの場合、セッション情報を更新
                if validated_data['event'] == 'conversion' and not session.converted:
                    session.converted = True
                    session.conversion_date = timezone.now()
                    session.save()
                
                logger.info(f'A/B test event tracked: {event}')
            
            return Response({
                'status': 'success',
                'message': 'Event tracked successfully',
                'event_id': event.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f'A/B test tracking error: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        """クライアントのIPアドレスを取得"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ABTestStatsView(APIView):
    """A/Bテスト統計情報取得 API"""
    
    permission_classes = [AllowAny]  # 本番環境では適切な権限設定を行う
    
    def get(self, request):
        """A/Bテストの統計情報を取得"""
        try:
            # 期間パラメータの取得（デフォルト：過去30日）
            days = int(request.GET.get('days', 30))
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 期間指定がある場合
            if request.GET.get('start_date'):
                start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
            if request.GET.get('end_date'):
                end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
            
            stats = {}
            
            for variant in ['A', 'B']:
                # 期間内のイベントを取得
                events = ABTestEvent.objects.filter(
                    variant=variant,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )
                
                # セッション情報を取得
                sessions = ABTestSession.objects.filter(
                    variant=variant,
                    first_visit__date__gte=start_date,
                    first_visit__date__lte=end_date
                )
                
                # 各種カウント
                page_views = events.filter(event='page_view').count()
                register_clicks = events.filter(event='register_click').count()
                login_clicks = events.filter(event='login_click').count()
                conversions = events.filter(event='conversion').count()
                unique_sessions = sessions.count()
                
                # 率の計算
                conversion_rate = conversions / unique_sessions if unique_sessions > 0 else 0
                click_through_rate = register_clicks / page_views if page_views > 0 else 0
                
                stats[f'variant{variant}'] = {
                    'pageViews': page_views,
                    'registerClicks': register_clicks,
                    'loginClicks': login_clicks,
                    'conversions': conversions,
                    'uniqueSessions': unique_sessions,
                    'conversionRate': round(conversion_rate, 4),
                    'clickThroughRate': round(click_through_rate, 4)
                }
            
            response_data = {
                'summary': stats,
                'period': {
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d')
                },
                'totalDays': (end_date - start_date).days + 1
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'A/B test stats error: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ABTestDailyStatsView(APIView):
    """A/Bテスト日別統計情報取得 API"""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """日別の統計情報を取得"""
        try:
            # 期間パラメータの取得
            days = int(request.GET.get('days', 30))
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 日別データを取得
            daily_data = []
            current_date = start_date
            
            while current_date <= end_date:
                day_stats = {'date': current_date.strftime('%Y-%m-%d')}
                
                for variant in ['A', 'B']:
                    events = ABTestEvent.objects.filter(
                        variant=variant,
                        created_at__date=current_date
                    )
                    
                    sessions = ABTestSession.objects.filter(
                        variant=variant,
                        first_visit__date=current_date
                    )
                    
                    page_views = events.filter(event='page_view').count()
                    register_clicks = events.filter(event='register_click').count()
                    conversions = events.filter(event='conversion').count()
                    unique_sessions = sessions.count()
                    
                    conversion_rate = conversions / unique_sessions if unique_sessions > 0 else 0
                    
                    day_stats[f'variant{variant}'] = {
                        'pageViews': page_views,
                        'registerClicks': register_clicks,
                        'conversions': conversions,
                        'uniqueSessions': unique_sessions,
                        'conversionRate': round(conversion_rate, 4)
                    }
                
                daily_data.append(day_stats)
                current_date += timedelta(days=1)
            
            return Response({
                'dailyStats': daily_data,
                'period': {
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d')
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'A/B test daily stats error: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ABTestEventsView(APIView):
    """A/Bテストイベント一覧取得 API（管理用）"""
    
    permission_classes = [AllowAny]  # 本番環境では管理者権限を設定
    
    def get(self, request):
        """イベント一覧を取得"""
        try:
            # フィルタリングパラメータ
            variant = request.GET.get('variant')
            event_type = request.GET.get('event')
            session_id = request.GET.get('session_id')
            limit = int(request.GET.get('limit', 100))
            
            # クエリセット構築
            queryset = ABTestEvent.objects.all()
            
            if variant:
                queryset = queryset.filter(variant=variant)
            if event_type:
                queryset = queryset.filter(event=event_type)
            if session_id:
                queryset = queryset.filter(session_id=session_id)
            
            # 最新順でlimit件取得
            events = queryset.order_by('-created_at')[:limit]
            
            serializer = ABTestEventSerializer(events, many=True)
            
            return Response({
                'events': serializer.data,
                'total': queryset.count(),
                'limit': limit
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'A/B test events error: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )