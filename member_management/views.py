# Django
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from pydantic import ValidationError
# Django REST Framework
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
# Local imports
from member_management.services import UserService, OrganizationService
from .serializers import (
    OrganizationSerializer,
    UserSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer
)
from .models import User, Organization, SubscriptionPlan, Subscription, CampaignTracking
from .schemas import UserCreateData, OrganizationCreateData
# Standard library
import json
import logging
import random
import string
# Third-party
import stripe
from stripe.error import StripeError, CardError, InvalidRequestError, AuthenticationError

api_logger = logging.getLogger('django')

class RegisterView(View):
    def post(self, request):
        api_logger.info(f"Register request: {request.POST}")
        request_data = json.loads(request.body)

        try:
            organization_data = OrganizationCreateData(**request_data)
            user_data = UserCreateData(**request_data)

            with transaction.atomic():
                organization = OrganizationService.create_organization(organization_data)
                user_service = UserService(organization)
                user = user_service.create_user(user_data, is_register_view=True)

                # キャンペーントラッキングの更新
                # 1. フロントエンドから送信されたセッションIDを優先
                campaign_session_id = user_data.campaign_session_id or request.session.get('campaign_session_id')
                if campaign_session_id:
                    try:
                        tracking = CampaignTracking.objects.filter(
                            session_id=campaign_session_id,
                            registered_user__isnull=True
                        ).first()
                        if tracking:
                            tracking.registered_user = user
                            tracking.registered_at = timezone.now()
                            tracking.save()
                            api_logger.info(f"Campaign tracking updated for user {user.id}, source: {tracking.source}")
                        else:
                            # フロントエンドからUTMデータが送信されている場合は新規作成
                            if user_data.utm_source:
                                source_map = {
                                    'flyer': CampaignTracking.Source.FLYER,
                                    'web': CampaignTracking.Source.WEB,
                                    'social': CampaignTracking.Source.SOCIAL,
                                    'friend': CampaignTracking.Source.FRIEND,
                                    'news': CampaignTracking.Source.NEWS,
                                    'other': CampaignTracking.Source.OTHER,
                                }
                                source = source_map.get(user_data.utm_source, CampaignTracking.Source.OTHER)

                                CampaignTracking.objects.create(
                                    source=source,
                                    session_id=campaign_session_id,
                                    registered_user=user,
                                    registered_at=timezone.now(),
                                    accessed_at=timezone.now(),
                                    is_manual_referral=user_data.manual_referral or False
                                )

                                referral_type = "手動設定" if user_data.manual_referral else "自動取得"
                                api_logger.info(f"New campaign tracking created for user {user.id}, source: {user_data.utm_source} ({referral_type})")
                    except Exception as e:
                        api_logger.error(f"Failed to update campaign tracking: {e}")

                try:
                    UserService.send_verification_email(user)
                    # 管理者に新規会員登録の通知を送信
                    UserService.send_admin_notification_email(user)
                except Exception as e:
                    api_logger.error(f"User registration email sending failed: {e}")
                    raise

            api_logger.info(f"User registration successful: {user.id}")
            return JsonResponse({'message': 'メール認証リンクを送信しました。'}, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            # Pydanticの複数バリデーションエラーを処理
            api_logger.error(f"User registration validation error: {e}")
            errors = {}
            for error in e.errors():
                field = error['loc'][0] if error['loc'] else 'unknown'
                # エラーメッセージから具体的な内容を抽出
                error_msg = str(error.get('msg', ''))
                if 'メールアドレスが既に存在します' in error_msg:
                    errors[field] = 'メールアドレスが既に存在します'
                elif '電話番号が既に存在します' in error_msg:
                    errors[field] = '電話番号が既に存在します'
                elif '無効なメールアドレスです' in error_msg:
                    errors[field] = '無効なメールアドレスです'
                elif '無効な電話番号です' in error_msg:
                    errors[field] = '無効な電話番号です'
                elif 'パスワードは8文字以上である必要があります' in error_msg:
                    errors[field] = 'パスワードは8文字以上である必要があります'
                else:
                    errors[field] = error_msg

            return JsonResponse({
                'message': '入力内容に誤りがあります',
                'errors': errors,
                'error_type': 'validation'
            }, status=status.HTTP_400_BAD_REQUEST)

        except ValueError as e:
            api_logger.error(f"User registration validation error: {e}")
            error_msg = str(e)
            # エラーの種類を判別してフィールド情報を追加
            if 'メールアドレスが既に存在します' in error_msg:
                return JsonResponse({
                    'message': error_msg,
                    'field': 'email',
                    'error_type': 'duplicate'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif '電話番号が既に存在します' in error_msg:
                return JsonResponse({
                    'message': error_msg,
                    'field': 'phone_number',
                    'error_type': 'duplicate'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif '無効なメールアドレスです' in error_msg:
                return JsonResponse({
                    'message': error_msg,
                    'field': 'email',
                    'error_type': 'invalid'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif '無効な電話番号です' in error_msg:
                return JsonResponse({
                    'message': error_msg,
                    'field': 'phone_number',
                    'error_type': 'invalid'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif 'パスワードは8文字以上である必要があります' in error_msg:
                return JsonResponse({
                    'message': error_msg,
                    'field': 'password',
                    'error_type': 'invalid'
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return JsonResponse({
                    'message': error_msg,
                    'error_type': 'validation'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            api_logger.error(f"User registration failed: {e}")
            return JsonResponse({
                'message': 'ユーザーが作成できませんでした',
                'error_type': 'server'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        organization = user.organization

        # 運営の場合は全組織のデータを返す
        if user.is_staff or user.is_superuser:
            return Organization.objects.all()

        # 管理者、一般ユーザーの場合は自分の組織のデータを返す
        return Organization.objects.filter(id=organization.id)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.get_queryset_by_login_user(self.request.user)

    def perform_create(self, serializer):
        user_data = UserCreateData(**serializer.validated_data)
        user_service = UserService(self.request.user.organization)
        user = user_service.create_user(user_data, is_register_view=False)

        try:
            UserService.send_verification_email(user)
        except Exception as e:
            api_logger.error(f"User registration email sending failed: {e}")
            raise

    @action(detail=False, methods=['get'])
    def me(self, request):
        # 現在のユーザーの情報のみをシリアライズして返す
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def password_change(self, request):
        user = request.user
        if not user.check_password(request.data['current_password']):
            return Response({'message': '古いパスワードが間違っています'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(request.data['new_password'])
        user.save()
        return Response({'message': 'パスワードを変更しました'})

class EmailVerificationView(View):
    def get(self, request, uidb64):
        try:
            return UserService.verify_email(request, uidb64)
        except Exception as e:
            return JsonResponse({'message': 'メール認証に失敗しました'}, status=status.HTTP_400_BAD_REQUEST)

class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            username = request.data.get('username')
            user = User.objects.get(username=username)

            if UserService.is_locked(user):
                return JsonResponse(
                    {'message': 'アカウントがロックされています。30分後に再試行してください。'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if user.two_factor_enabled:
                two_factor_code = ''.join(random.choices(string.digits, k=6))
                random_key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                two_factor_cache_key = f"2fa_{random_key}"
                cache.set(two_factor_cache_key, {
                    'two_factor_code': two_factor_code,
                    'timestamp': timezone.now().timestamp()
                }, timeout=300)

                UserService.send_two_factor_code(user, two_factor_code)

                return JsonResponse({
                    'message': '2要素認証が必要です',
                    'requires_two_factor': True,
                    'two_factor_method': user.two_factor_method,
                    'key': two_factor_cache_key,
                    'access': response.data.get('access'),
                    'refresh': response.data.get('refresh')
                }, status=status.HTTP_200_OK)

            UserService.reset_login_attempts(user)
            return response

        try:
            user = User.objects.get(username=request.data.get('username'))
            UserService.increment_login_attempts(user)
        except User.DoesNotExist:
            pass

        return response

class TwoFactorVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = json.loads(request.body)
            two_factor_code = data.get('code')
            two_factor_cache_key = data.get('key')
        except json.JSONDecodeError:
            return JsonResponse({'message': '認証情報が無効です'}, status=status.HTTP_400_BAD_REQUEST)

        stored_data = cache.get(two_factor_cache_key)
        if not stored_data:
            return JsonResponse({'message': '認証情報が無効です'}, status=status.HTTP_400_BAD_REQUEST)

        stored_two_factor_code = stored_data.get('two_factor_code')
        expiration_time = stored_data.get('timestamp')

        if timezone.now().timestamp() - expiration_time > 300:
            cache.delete(two_factor_cache_key)
            return JsonResponse({'message': '認証コードの有効期限が切れています'}, status=status.HTTP_400_BAD_REQUEST)

        if two_factor_code == stored_two_factor_code:
            UserService.reset_login_attempts(request.user)
            cache.delete(two_factor_cache_key)
            return JsonResponse({'message': '認証成功'},status=status.HTTP_200_OK)

        return JsonResponse({'message': '認証コードが間違っています'}, status=status.HTTP_400_BAD_REQUEST)

class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer

class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        user = self.request.user
        return Subscription.objects.filter(organization=user.organization)

    def list(self, request, *args, **kwargs):
        """組織のサブスクリプション情報を単一オブジェクトとして返す"""
        queryset = self.get_queryset()
        api_logger.info(f"Subscription list request for user {request.user.id}, organization {request.user.organization.id}")

        if queryset.exists():
            instance = queryset.first()
            serializer = self.get_serializer(instance)
            api_logger.info(f"Found subscription: {instance.id}, status: {instance.status}")
            return Response(serializer.data)
        else:
            api_logger.info("No subscription found for organization")
            return Response(None)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def create_checkout_session(self, request):
        """Stripeのチェックアウトセッションを作成"""
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            plan_id = request.data.get('plan_id')

            if not plan_id:
                return Response(
                    {'error': 'プランIDが必要です'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            except SubscriptionPlan.DoesNotExist:
                return Response(
                    {'error': '指定されたプランが見つかりません'},
                    status=status.HTTP_404_NOT_FOUND
                )

            organization = request.user.organization

            subscription, created = Subscription.objects.get_or_create(
                organization=organization,
                defaults={
                    'status': Subscription.Status.INACTIVE,
                    'has_used_trial': True  # 安全のため新規作成時はトライアル済みとする
                }
            )

            if not subscription.stripe_customer_id:
                try:
                    customer = stripe.Customer.create(
                        email=request.user.email,
                        name=f"{organization.name} ({request.user.last_name} {request.user.first_name})",
                        metadata={
                            'organization_id': str(organization.id),
                            'user_id': str(request.user.id)
                        }
                    )
                    subscription.stripe_customer_id = customer.id
                    subscription.save()
                    api_logger.info(f"Created Stripe customer {customer.id} for organization {organization.id}")
                except StripeError as e:
                    api_logger.error(f"Failed to create Stripe customer: {e}")
                    return Response(
                        {'error': '顧客情報の作成に失敗しました'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            success_url = f"{settings.NEXT_JS_HOST}/mypage?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{settings.NEXT_JS_HOST}/mypage"

            # トライアル期間の設定（既に使用済みの場合は0日）
            trial_days = 0 if subscription.has_used_trial else 30

            try:
                # チェックアウトセッションの基本設定
                session_params = {
                    'customer': subscription.stripe_customer_id,
                    'payment_method_types': ['card'],
                    'line_items': [{
                        'price': plan.stripe_price_id,
                        'quantity': 1,
                    }],
                    'mode': 'subscription',
                    'success_url': success_url,
                    'cancel_url': cancel_url,
                    'metadata': {
                        'organization_id': str(organization.id),
                        'plan_id': str(plan.id)
                    }
                }

                # トライアルが利用可能な場合のみ追加
                if trial_days > 0:
                    session_params['subscription_data'] = {
                        'trial_period_days': trial_days,
                        'trial_settings': {
                            'end_behavior': {
                                'missing_payment_method': 'cancel'
                            }
                        }
                    }
                    api_logger.info(f"Creating checkout session with {trial_days} day trial for organization {organization.id}")
                else:
                    api_logger.info(f"Creating checkout session without trial (already used) for organization {organization.id}")

                checkout_session = stripe.checkout.Session.create(**session_params)
                api_logger.info(f"Created checkout session {checkout_session.id} for organization {organization.id}")
                return Response({'checkout_url': checkout_session.url})

            except StripeError as e:
                api_logger.error(f"Failed to create checkout session: {e}")
                if isinstance(e, CardError):
                    return Response(
                        {'error': 'カード情報に問題があります'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                elif isinstance(e, InvalidRequestError):
                    return Response(
                        {'error': '無効なリクエストです'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    return Response(
                        {'error': 'チェックアウトセッションの作成に失敗しました'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

        except Exception as e:
            api_logger.error(f"Unexpected error in create_checkout_session: {e}")
            return Response(
                {'error': 'システムエラーが発生しました'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def manage_portal(self, request):
        """Stripeの顧客ポータルセッションを作成"""
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            organization = request.user.organization

            try:
                subscription = Subscription.objects.get(organization=organization)
            except Subscription.DoesNotExist:
                return Response(
                    {'error': 'サブスクリプションが存在しません'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if not subscription.stripe_customer_id:
                return Response(
                    {'error': 'Stripe顧客IDが設定されていません'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return_url = f"{settings.NEXT_JS_HOST}/mypage"

            try:
                portal_session = stripe.billing_portal.Session.create(
                    customer=subscription.stripe_customer_id,
                    return_url=return_url,
                )
                api_logger.info(f"Created portal session for customer {subscription.stripe_customer_id}")
                return Response({'portal_url': portal_session.url})

            except StripeError as e:
                api_logger.error(f"Failed to create portal session: {e}")
                return Response(
                    {'error': 'ポータルセッションの作成に失敗しました'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            api_logger.error(f"Unexpected error in manage_portal: {e}")
            return Response(
                {'error': 'システムエラーが発生しました'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        if not webhook_secret:
            api_logger.error("Stripe webhook secret is not configured")
            return HttpResponse(status=400)

        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not sig_header:
            api_logger.error("Missing Stripe signature header")
            return HttpResponse(status=400)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            api_logger.info(f"Received Stripe webhook: {event['type']}")
        except ValueError as e:
            api_logger.error(f"Invalid payload: {e}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            api_logger.error(f"Invalid signature: {e}")
            return HttpResponse(status=400)

        try:
            api_logger.info(f"Processing webhook event: {event['type']}")
            api_logger.debug(f"Webhook event data: {event['data']}")

            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                api_logger.info(f"Processing checkout.session.completed for session {session.get('id')}")
                fulfill_subscription(session)
            elif event['type'] == 'customer.subscription.updated':
                subscription = event['data']['object']
                api_logger.info(f"Processing customer.subscription.updated for subscription {subscription.get('id')}")
                update_subscription(subscription)
            elif event['type'] == 'customer.subscription.deleted':
                subscription = event['data']['object']
                api_logger.info(f"Processing customer.subscription.deleted for subscription {subscription.get('id')}")
                cancel_subscription(subscription)
            elif event['type'] == 'invoice.payment_failed':
                invoice = event['data']['object']
                api_logger.warning(f"Payment failed for invoice {invoice['id']}")
            elif event['type'] == 'invoice.payment_succeeded':
                invoice = event['data']['object']
                api_logger.info(f"Payment succeeded for invoice {invoice['id']}")
            else:
                api_logger.info(f"Unhandled webhook event: {event['type']}")

        except Exception as e:
            api_logger.error(f"Error processing webhook {event['type']}: {e}")
            api_logger.error(f"Exception details: {str(e)}")
            import traceback
            api_logger.error(f"Traceback: {traceback.format_exc()}")
            return HttpResponse(status=500)

        return HttpResponse(status=200)


def fulfill_subscription(session):
    """チェックアウト完了時の処理"""
    api_logger.info(f"Starting fulfill_subscription for session {session.get('id')}")
    api_logger.debug(f"Session data: {session}")

    org_id = session.get('metadata', {}).get('organization_id')
    plan_id = session.get('metadata', {}).get('plan_id')

    api_logger.info(f"Organization ID: {org_id}, Plan ID: {plan_id}")

    try:
        organization = Organization.objects.get(id=org_id)
        plan = SubscriptionPlan.objects.get(id=plan_id)
        api_logger.info(f"Found organization: {organization.name}, plan: {plan.name}")

        subscription, created = Subscription.objects.get_or_create(
            organization=organization,
            defaults={
                'plan': plan,
                'status': Subscription.Status.ACTIVE,
                'stripe_customer_id': session.get('customer'),
                'stripe_subscription_id': session.get('subscription')
            }
        )

        if created:
            api_logger.info(f"New subscription created for organization {organization.id} with plan {plan.id}")
        else:
            api_logger.info(f"Existing subscription found for organization {organization.id}. Current plan: {subscription.plan.id if subscription.plan else 'None'}")
            subscription.plan = plan
            subscription.status = Subscription.Status.ACTIVE
            subscription.stripe_subscription_id = session.get('subscription')
            subscription.save()
            api_logger.info(f"Existing subscription updated to plan {subscription.plan.id}")

        stripe_subscription = stripe.Subscription.retrieve(session.get('subscription'))

        subscription.current_period_start = timezone.datetime.fromtimestamp(
            stripe_subscription.current_period_start
        )
        subscription.current_period_end = timezone.datetime.fromtimestamp(
            stripe_subscription.current_period_end
        )
        subscription.save()

    except (Organization.DoesNotExist, SubscriptionPlan.DoesNotExist) as e:
        api_logger.error(f"Error processing subscription fulfillment: {e}")
        api_logger.error(f"Organization ID from metadata: {org_id}")
        api_logger.error(f"Plan ID from metadata: {plan_id}")
        api_logger.error(f"Available organizations: {list(Organization.objects.values_list('id', 'name'))}")
        api_logger.error(f"Available plans: {list(SubscriptionPlan.objects.values_list('id', 'name'))}")


def update_subscription(stripe_subscription):
    """サブスクリプション更新時の処理"""
    try:
        # まずstripe_subscription_idで検索（既存レコード用）
        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription['id']
        ).first()

        # stripe_subscription_idが未登録の場合はstripe_customer_idで検索
        if not subscription:
            subscription = Subscription.objects.filter(
                stripe_customer_id=stripe_subscription['customer']
            ).first()

        if not subscription:
            api_logger.error(f"Subscription not found for Stripe subscription ID: {stripe_subscription['id']} or customer ID: {stripe_subscription['customer']}")
            return

        # サブスクリプションIDを必ず更新
        subscription.stripe_subscription_id = stripe_subscription['id']

        # プラン情報の更新
        if stripe_subscription.get('plan') and stripe_subscription['plan'].get('id'):
            try:
                stripe_price_id = stripe_subscription['plan']['id']
                plan = SubscriptionPlan.objects.get(stripe_price_id=stripe_price_id)
                subscription.plan = plan
                api_logger.info(f"Subscription plan updated to {plan.id} for subscription {subscription.id}")
            except SubscriptionPlan.DoesNotExist:
                api_logger.error(f"SubscriptionPlan with stripe_price_id {stripe_price_id} not found.")
        else:
            api_logger.warning(f"No plan information found in stripe_subscription object for subscription {subscription.id}")

        # ステータス更新
        if stripe_subscription['status'] == 'active':
            subscription.status = Subscription.Status.ACTIVE
        elif stripe_subscription['status'] == 'past_due':
            subscription.status = Subscription.Status.PAST_DUE
        elif stripe_subscription['status'] == 'canceled':
            subscription.status = Subscription.Status.CANCELED
        elif stripe_subscription['status'] == 'trialing':
            subscription.status = Subscription.Status.TRIAL
            # トライアル開始時にフラグを更新
            if not subscription.has_used_trial:
                subscription.has_used_trial = True
                api_logger.info(f"Trial started for subscription {subscription.id}, marking has_used_trial=True")
        else:
            subscription.status = Subscription.Status.INACTIVE

        # 期間情報も更新
        subscription.current_period_start = timezone.datetime.fromtimestamp(
            stripe_subscription['current_period_start']
        )
        subscription.current_period_end = timezone.datetime.fromtimestamp(
            stripe_subscription['current_period_end']
        )
        subscription.cancel_at_period_end = stripe_subscription.get('cancel_at_period_end', False)
        subscription.save()

    except Exception as e:
        api_logger.error(f"Error updating subscription: {e}")


def cancel_subscription(stripe_subscription):
    """サブスクリプション削除時の処理"""
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription.id
        )
        subscription.status = Subscription.Status.CANCELED
        subscription.save()

    except Subscription.DoesNotExist:
        api_logger.error(f"Subscription not found for Stripe subscription ID: {stripe_subscription.id}")
