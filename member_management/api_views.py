from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from .models import CampaignTracking
import json
import logging
import uuid

logger = logging.getLogger('django')


@method_decorator(csrf_exempt, name='dispatch')
class TrackCampaignView(View):
    """フロントエンドからのキャンペーントラッキング用API"""

    def post(self, request):
        try:
            data = json.loads(request.body)

            # セッションIDの取得または生成
            session_id = data.get('session_id') or str(uuid.uuid4())

            # ソースの変換
            source_map = {
                'flyer': CampaignTracking.Source.FLYER,
                'web': CampaignTracking.Source.WEB,
                'social': CampaignTracking.Source.SOCIAL,
            }
            source = source_map.get(data.get('utm_source'), CampaignTracking.Source.OTHER)

            # IPアドレスの取得
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            # トラッキング情報を保存（重複チェック付き）
            tracking, created = CampaignTracking.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'source': source,
                    'ip_address': ip_address,
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'referer': request.META.get('HTTP_REFERER', ''),
                    'accessed_at': timezone.now()
                }
            )

            if created:
                logger.info(f"Campaign access tracked: session_id={session_id}, source={source}, ip={ip_address}")
            else:
                logger.debug(f"Campaign access already exists: session_id={session_id}")

            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'message': 'Campaign tracked successfully'
            })

        except json.JSONDecodeError:
            logger.error("Invalid JSON in campaign tracking request")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Failed to track campaign: {e}")
            return JsonResponse({'error': 'Tracking failed'}, status=500)


class CampaignStatsAPIView(View):
    """キャンペーン統計情報をJSON形式で返すAPI"""

    def get(self, request):
        # 管理者権限チェック
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        try:
            # 統計情報を取得
            flyer_stats = CampaignTracking.get_stats(source=CampaignTracking.Source.FLYER)
            all_stats = CampaignTracking.get_stats()

            # 最近のアクセス
            recent_flyer_access = list(CampaignTracking.objects.filter(
                source=CampaignTracking.Source.FLYER
            ).order_by('-accessed_at')[:10].values(
                'accessed_at', 'session_id', 'ip_address', 'registered_user__email'
            ))

            # 最近の登録
            recent_registrations = list(CampaignTracking.objects.filter(
                source=CampaignTracking.Source.FLYER,
                registered_user__isnull=False
            ).order_by('-registered_at')[:10].values(
                'registered_at', 'accessed_at', 'registered_user__email'
            ))

            return JsonResponse({
                'flyer_stats': flyer_stats,
                'all_stats': all_stats,
                'recent_flyer_access': recent_flyer_access,
                'recent_registrations': recent_registrations
            })

        except Exception as e:
            logger.error(f"Failed to get campaign stats: {e}")
            return JsonResponse({'error': 'Failed to get stats'}, status=500)