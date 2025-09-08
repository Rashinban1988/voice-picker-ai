from django.http import JsonResponse, HttpResponse, Http404
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
import os
from django.conf import settings
from .models import TrackingProject, PageView, UserInteraction, HeatmapData, ScrollDepth
from django.shortcuts import get_object_or_404, render
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

    def options(self, request):
        """CORS preflight request handler"""
        response = JsonResponse({})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    def post(self, request):
        print("DEBUG - PageViewCreateAPIView.post called")

        def get_client_ip(request):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            # Default to localhost if no IP is found
            return ip or '127.0.0.1'

        try:
            if hasattr(request, 'data') and request.data:
                data = request.data
            else:
                data = json.loads(request.body.decode('utf-8'))

            client_ip = get_client_ip(request)
            logger.info(f"Client IP detected: {client_ip}")
            # 既にip_addressが設定されていない場合のみ自動取得IPを使用
            if 'ip_address' not in data or not data['ip_address']:
                data['ip_address'] = client_ip

            print(f"DEBUG - Request data: {data}")
            print(f"DEBUG - Request method: {request.method}")
            print(f"DEBUG - Request headers: {dict(request.headers)}")

            serializer = PageViewSerializer(data=data)
            print(f"DEBUG - Serializer is_valid: {serializer.is_valid()}")
            if not serializer.is_valid():
                print(f"DEBUG - Serializer errors: {serializer.errors}")
                print(f"DEBUG - Validation failed, not calling create method")
            if serializer.is_valid():
                page_view = serializer.save()
                logger.info(f"Page view created: {page_view.id} for project {page_view.project.tracking_id}")

                response = JsonResponse({
                    'success': True,
                    'page_view_id': str(page_view.id)
                })

                # CORS対応
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'POST'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

                return response
            else:
                logger.warning(f"Page view creation failed: {serializer.errors}")
                print(f"DEBUG - Data received: {data}")
                print(f"DEBUG - Validation errors: {serializer.errors}")
                # ValidationErrorをキャッチして500エラーとして扱わず、400エラーとして返す
                response = JsonResponse({
                    'success': False,
                    'errors': serializer.errors
                }, status=400)
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'POST'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                return response

        except Exception as e:
            import traceback
            from rest_framework import serializers
            logger.error(f"Page view creation error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            print(f"DEBUG - Exception: {e}")
            print(f"DEBUG - Traceback: {traceback.format_exc()}")

            # ValidationErrorの場合は400エラーとして返す
            if isinstance(e, serializers.ValidationError):
                response = JsonResponse({
                    'success': False,
                    'errors': e.detail if hasattr(e, 'detail') else str(e)
                }, status=400)
            else:
                response = JsonResponse({
                    'success': False,
                    'error': 'Internal server error',
                    'debug_error': str(e)
                }, status=500)

            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'POST'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response


@method_decorator(csrf_exempt, name='dispatch')
class InteractionCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def options(self, request):
        """CORS preflight request handler"""
        response = JsonResponse({})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    def post(self, request):
        try:
            data = json.loads(request.body) if isinstance(request.body, bytes) else request.data

            if 'events' in data:
                serializer = BatchInteractionSerializer(data=data)
                if serializer.is_valid():
                    interactions = serializer.save()
                    logger.info(f"Batch interactions created: {len(interactions)} events")

                    response = JsonResponse({
                        'success': True,
                        'created_count': len(interactions)
                    })

                    # CORS対応
                    response['Access-Control-Allow-Origin'] = '*'
                    response['Access-Control-Allow-Methods'] = 'POST'
                    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

                    return response
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

                    response = JsonResponse({
                        'success': True,
                        'interaction_id': str(interaction.id)
                    })

                    # CORS対応
                    response['Access-Control-Allow-Origin'] = '*'
                    response['Access-Control-Allow-Methods'] = 'POST'
                    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

                    return response
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


@method_decorator(csrf_exempt, name='dispatch')
class AnalyticsDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]  # 開発環境では認証を簡単にする

    @action(detail=True, methods=['get'])
    def heatmap_data(self, request, pk=None):
        """ヒートマップデータの取得"""
        try:
            project = TrackingProject.objects.get(id=pk)

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

            response = Response({
                'success': True,
                'data': heatmap_data,
                'total_clicks': len(heatmap_data)
            })

            # CORS対応
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

            return response

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
            project = TrackingProject.objects.get(id=pk)

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


def test_page_view(request, tracking_id):
    """ヒートマップテスト用のページ"""
    project = get_object_or_404(TrackingProject, tracking_id=tracking_id, is_active=True)

    context = {
        'project': project,
        'tracking_id': tracking_id,
    }

    return render(request, 'analytics/test_page.html', context)


def cdn_sdk_serve(request):
    """CDN SDK配信エンドポイント"""
    try:
        # 静的ファイルパスを構築
        sdk_path = os.path.join(settings.STATIC_ROOT, 'js', 'lp-analytics-cdn.js')

        # 開発環境では静的ファイルが別の場所にある場合
        if not os.path.exists(sdk_path):
            sdk_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'lp-analytics-cdn.js')

        if not os.path.exists(sdk_path):
            raise Http404("SDK file not found")

        # ファイルを読み込み
        with open(sdk_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # CORS対応のレスポンス
        response = HttpResponse(content, content_type='application/javascript')
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Cache-Control'] = 'public, max-age=3600'  # 1時間キャッシュ

        return response

    except Exception as e:
        logger.error(f"SDK serving error: {e}")
        return HttpResponse("SDK not available", status=404)
