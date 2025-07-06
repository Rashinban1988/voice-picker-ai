import logging
from django.http import HttpResponseForbidden
from django.conf import settings

logger = logging.getLogger('django')


class StripeSecurityMiddleware:
    """
    Stripeのセキュリティを強化するミドルウェア
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Stripe Webhookエンドポイントのセキュリティチェック
        if request.path.endswith('/webhook/stripe/'):
            return self.handle_stripe_webhook(request)
        
        return self.get_response(request)
    
    def handle_stripe_webhook(self, request):
        """Stripe Webhookのセキュリティチェック"""
        # Content-Typeの確認
        content_type = request.META.get('CONTENT_TYPE', '')
        if not content_type.startswith('application/json'):
            logger.warning(f"Invalid content type for Stripe webhook: {content_type}")
            return HttpResponseForbidden("Invalid content type")
        
        # User-Agentの確認（Stripeからのリクエストかどうか）
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not user_agent.startswith('Stripe/v1'):
            logger.warning(f"Suspicious User-Agent for Stripe webhook: {user_agent}")
            # 本番環境では厳密にチェックするが、開発環境では警告のみ
        
        # リクエストサイズの制限
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length and int(content_length) > 1024 * 1024:  # 1MB制限
            logger.warning(f"Stripe webhook payload too large: {content_length} bytes")
            return HttpResponseForbidden("Payload too large")
        
        return self.get_response(request)


class SubscriptionAccessMiddleware:
    """
    サブスクリプション状態に基づくアクセス制御ミドルウェア
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # 認証済みユーザーのみチェック
        if hasattr(request, 'user') and request.user.is_authenticated:
            self.check_subscription_access(request)
        
        return self.get_response(request)
    
    def check_subscription_access(self, request):
        """サブスクリプション状態をチェック"""
        from member_management.models import Subscription
        
        # 特定のエンドポイントのみチェック
        protected_paths = [
            '/api/voice-picker/',
            '/api/calendar/',
            # 他の保護されたエンドポイントを追加
        ]
        
        if not any(request.path.startswith(path) for path in protected_paths):
            return
        
        try:
            subscription = Subscription.objects.get(organization=request.user.organization)
            
            # アクティブなサブスクリプションがない場合
            if not subscription.is_active():
                logger.warning(f"User {request.user.id} attempted to access protected endpoint without active subscription")
                # ここでリダイレクトやエラーレスポンスを返すことも可能
                
        except Subscription.DoesNotExist:
            logger.warning(f"User {request.user.id} has no subscription record")
            # サブスクリプションが存在しない場合の処理 