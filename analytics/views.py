from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
import json
import logging
from .models import TrackingProject, PageView, UserInteraction, HeatmapData, ScrollDepth
from .serializers import (
    PageViewSerializer, 
    UserInteractionSerializer, 
    BatchInteractionSerializer,
    TrackingProjectSerializer
)

logger = logging.getLogger('django')


class TrackingProjectViewSet(viewsets.ModelViewSet):
    serializer_class = TrackingProjectSerializer
    
    def get_queryset(self):
        return TrackingProject.objects.filter(organization=self.request.user.organization)
    
    def perform_create(self, serializer):
        import secrets
        import string
        
        tracking_id = 'lp_' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        serializer.save(
            organization=self.request.user.organization,
            tracking_id=tracking_id
        )


@method_decorator(csrf_exempt, name='dispatch')
class PageViewCreateAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        def get_client_ip(request):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            # Default to localhost if no IP is found
            return ip or '127.0.0.1'
        
        try:
            data = json.loads(request.body) if isinstance(request.body, bytes) else request.data
            client_ip = get_client_ip(request)
            logger.info(f"Client IP detected: {client_ip}")
            data['ip_address'] = client_ip
            
            serializer = PageViewSerializer(data=data)
            if serializer.is_valid():
                page_view = serializer.save()
                logger.info(f"Page view created: {page_view.id} for project {page_view.project.tracking_id}")
                return JsonResponse({
                    'success': True,
                    'page_view_id': str(page_view.id)
                })
            else:
                logger.warning(f"Page view creation failed: {serializer.errors}")
                return JsonResponse({
                    'success': False,
                    'errors': serializer.errors
                }, status=400)
                
        except Exception as e:
            logger.error(f"Page view creation error: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class InteractionCreateAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            data = json.loads(request.body) if isinstance(request.body, bytes) else request.data
            
            if 'events' in data:
                serializer = BatchInteractionSerializer(data=data)
                if serializer.is_valid():
                    interactions = serializer.save()
                    logger.info(f"Batch interactions created: {len(interactions)} events")
                    return JsonResponse({
                        'success': True,
                        'created_count': len(interactions)
                    })
                else:
                    logger.warning(f"Batch interaction creation failed: {serializer.errors}")
                    return JsonResponse({
                        'success': False,
                        'errors': serializer.errors
                    }, status=400)
            else:
                serializer = UserInteractionSerializer(data=data)
                if serializer.is_valid():
                    interaction = serializer.save()
                    logger.info(f"Interaction created: {interaction.id}")
                    return JsonResponse({
                        'success': True,
                        'interaction_id': str(interaction.id)
                    })
                else:
                    logger.warning(f"Interaction creation failed: {serializer.errors}")
                    return JsonResponse({
                        'success': False,
                        'errors': serializer.errors
                    }, status=400)
                    
        except Exception as e:
            logger.error(f"Interaction creation error: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)


class AnalyticsDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    @action(detail=True, methods=['get'])
    def heatmap_data(self, request, pk=None):
        """ヒートマップデータの取得"""
        try:
            project = TrackingProject.objects.get(
                id=pk, 
                organization=request.user.organization
            )
            
            page_url = request.query_params.get('page_url')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            
            interactions = UserInteraction.objects.filter(
                page_view__project=project,
                event_type='click'
            )
            
            if page_url:
                interactions = interactions.filter(page_view__page_url=page_url)
            
            if date_from:
                interactions = interactions.filter(created_at__gte=date_from)
            
            if date_to:
                interactions = interactions.filter(created_at__lte=date_to)
            
            heatmap_data = []
            for interaction in interactions:
                if interaction.x_coordinate and interaction.y_coordinate:
                    heatmap_data.append({
                        'x': interaction.x_coordinate,
                        'y': interaction.y_coordinate,
                        'value': 1
                    })
            
            return Response({
                'success': True,
                'data': heatmap_data,
                'total_clicks': len(heatmap_data)
            })
            
        except TrackingProject.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Project not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Heatmap data error: {e}")
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    @action(detail=True, methods=['get'])
    def scroll_data(self, request, pk=None):
        """スクロールデータの取得"""
        try:
            project = TrackingProject.objects.get(
                id=pk,
                organization=request.user.organization
            )
            
            page_url = request.query_params.get('page_url')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            
            interactions = UserInteraction.objects.filter(
                page_view__project=project,
                event_type='scroll',
                scroll_percentage__isnull=False
            ).order_by('scroll_percentage')
            
            if page_url:
                interactions = interactions.filter(page_view__page_url=page_url)
            
            if date_from:
                interactions = interactions.filter(created_at__gte=date_from)
            
            if date_to:
                interactions = interactions.filter(created_at__lte=date_to)
            
            scroll_data = {}
            for interaction in interactions:
                percentage = int(interaction.scroll_percentage)
                scroll_data[percentage] = scroll_data.get(percentage, 0) + 1
            
            return Response({
                'success': True,
                'data': scroll_data,
                'total_users': len(set(interactions.values_list('page_view__session_id', flat=True)))
            })
            
        except TrackingProject.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Project not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Scroll data error: {e}")
            return Response({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
