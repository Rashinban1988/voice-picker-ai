import json
import stripe
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from member_management.models import Organization, SubscriptionPlan, Subscription
from member_management.models.subscription import Subscription as SubscriptionModel

User = get_user_model()

# テスト時はStripe APIを呼び出さない
STRIPE_SECRET_KEY = 'sk_test_dummy'  # テスト用

class StripeTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # テスト用組織とユーザーを作成
        self.organization = Organization.objects.create(
            name="テスト組織",
            phone_number="090-1234-5678"
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            organization=self.organization,
            first_name="太郎",
            last_name="テスト",
            phone_number="090-1234-5678",
            is_active=True
        )
        
        # テスト用プランを作成
        self.plan = SubscriptionPlan.objects.create(
            name="テストプラン",
            description="テスト用プラン",
            price=1000,
            max_duration=100,
            stripe_price_id="price_test_123",
            is_active=True
        )


class StripeCheckoutSessionTest(StripeTestCase):
    @patch('stripe.Customer.create')
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_success(self, mock_session_create, mock_customer_create):
        """チェックアウトセッション作成の成功テスト"""
        # モックの設定
        mock_customer = MagicMock()
        mock_customer.id = "cus_test_123"
        mock_customer_create.return_value = mock_customer
        
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session_create.return_value = mock_session
        
        # ログイン
        self.client.force_login(self.user)
        
        # APIエンドポイントを呼び出し
        response = self.client.post(
            reverse('create_checkout_session'),
            data={'plan_id': str(self.plan.id)},
            content_type='application/json'
        )
        
        # レスポンスの検証
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('checkout_url', data)
        self.assertEqual(data['checkout_url'], "https://checkout.stripe.com/test")
        
        # モックが正しく呼ばれたことを確認
        mock_customer_create.assert_called_once()
        mock_session_create.assert_called_once()

    def test_create_checkout_session_no_plan_id(self):
        """プランIDが指定されていない場合のテスト"""
        self.client.force_login(self.user)
        
        response = self.client.post(
            reverse('create_checkout_session'),
            data={},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)

    def test_create_checkout_session_invalid_plan(self):
        """無効なプランIDの場合のテスト"""
        self.client.force_login(self.user)
        
        response = self.client.post(
            reverse('create_checkout_session'),
            data={'plan_id': 'invalid-uuid'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertIn('error', data)


class StripePortalTest(StripeTestCase):
    def setUp(self):
        super().setUp()
        # テスト用サブスクリプションを作成
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            stripe_customer_id="cus_test_123"
        )

    @patch('stripe.billing_portal.Session.create')
    def test_manage_portal_success(self, mock_portal_create):
        """顧客ポータル作成の成功テスト"""
        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/test"
        mock_portal_create.return_value = mock_portal
        
        self.client.force_login(self.user)
        
        response = self.client.post(
            reverse('manage_portal'),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('portal_url', data)
        self.assertEqual(data['portal_url'], "https://billing.stripe.com/test")

    def test_manage_portal_no_subscription(self):
        """サブスクリプションが存在しない場合のテスト"""
        # サブスクリプションを削除
        self.subscription.delete()
        
        self.client.force_login(self.user)
        
        response = self.client.post(
            reverse('manage_portal'),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('error', data)


class StripeWebhookTest(StripeTestCase):
    def setUp(self):
        super().setUp()
        self.webhook_secret = "whsec_test_secret"
        
    @patch('stripe.Webhook.construct_event')
    @patch('stripe.Subscription.retrieve')
    def test_webhook_checkout_session_completed(self, mock_construct_event, mock_subscription_retrieve):
        """チェックアウト完了Webhookのテスト"""
        # モックの設定
        mock_event = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_123',
                    'customer': 'cus_test_123',
                    'subscription': 'sub_test_123',
                    'metadata': {
                        'organization_id': str(self.organization.id),
                        'plan_id': str(self.plan.id)
                    }
                }
            }
        }
        mock_construct_event.return_value = mock_event
        
        # ダミーのサブスクリプションデータを作成
        mock_subscription = MagicMock()
        mock_subscription.current_period_start = 1640995200
        mock_subscription.current_period_end = 1643673600
        mock_subscription_retrieve.return_value = mock_subscription
        
        # Webhookリクエスト
        response = self.client.post(
            reverse('stripe_webhook'),
            data=json.dumps(mock_event),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        self.assertEqual(response.status_code, 200)

    @patch('stripe.Webhook.construct_event')
    def test_webhook_subscription_updated(self, mock_construct_event):
        """サブスクリプション更新Webhookのテスト"""
        # 既存のサブスクリプションを作成
        subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123"
        )
        
        # モックの設定
        mock_event = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_test_123',
                    'customer': 'cus_test_123',
                    'status': 'active',
                    'current_period_start': 1640995200,  # 2022-01-01
                    'current_period_end': 1643673600,    # 2022-02-01
                    'cancel_at_period_end': False
                }
            }
        }
        mock_construct_event.return_value = mock_event
        
        # Webhookリクエスト
        response = self.client.post(
            reverse('stripe_webhook'),
            data=json.dumps(mock_event),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        self.assertEqual(response.status_code, 200)


class StripeModelTest(StripeTestCase):
    def test_subscription_is_active(self):
        """サブスクリプションのアクティブ状態テスト"""
        subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            status=Subscription.Status.ACTIVE
        )
        
        self.assertTrue(subscription.is_active())
        
        subscription.status = Subscription.Status.TRIAL
        subscription.save()
        self.assertTrue(subscription.is_active())
        
        subscription.status = Subscription.Status.INACTIVE
        subscription.save()
        self.assertFalse(subscription.is_active())

    def test_subscription_within_contract_period(self):
        """契約期間内の判定テスト"""
        from django.utils import timezone
        import datetime
        
        now = timezone.now()
        start = now - datetime.timedelta(days=1)
        end = now + datetime.timedelta(days=1)
        
        subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            current_period_start=start,
            current_period_end=end
        )
        
        self.assertTrue(subscription.is_within_contract_period())
        
        # 期間外の場合
        subscription.current_period_end = now - datetime.timedelta(days=1)
        subscription.save()
        self.assertFalse(subscription.is_within_contract_period())


class StripeErrorHandlingTest(StripeTestCase):
    @patch('stripe.Customer.create')
    def test_stripe_error_handling(self, mock_customer_create):
        """Stripeエラーハンドリングのテスト"""
        # Stripeエラーを発生させる
        mock_customer_create.side_effect = stripe.error.StripeError("Test error")
        
        self.client.force_login(self.user)
        
        response = self.client.post(
            reverse('create_checkout_session'),
            data={'plan_id': str(self.plan.id)},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertIn('error', data)

# 既存のデータを確認
from member_management.models import Organization, SubscriptionPlan

# 既存の組織を確認
organizations = Organization.objects.all()
for org in organizations:
    print(f"組織: {org.id} - {org.name}")

# 既存のプランを確認
plans = SubscriptionPlan.objects.all()
for plan in plans:
    print(f"プラン: {plan.id} - {plan.name}")

# 最初の組織とプランを使用
if organizations.exists() and plans.exists():
    org = organizations.first()
    plan = plans.first()
    print(f"使用する組織: {org.id} - {org.name}")
    print(f"使用するプラン: {plan.id} - {plan.name}")
else:
    print("データが不足しています。上記のコードでデータを作成してください。") 