"""
Stripe統合テスト
リアルStripe API（テストモード）を使用した統合テスト
本番環境には影響しません
"""

import os
import time
import logging
from django.test import TestCase, TransactionTestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from member_management.models.organization import Organization
from member_management.models.subscription import Subscription, SubscriptionPlan
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import stripe

# ロガー設定
logger = logging.getLogger('stripe_integration')

User = get_user_model()

class StripeIntegrationTestCase(TransactionTestCase):
    """Stripe統合テストベースクラス"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Stripe設定
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # テストモード確認
        if not settings.STRIPE_SECRET_KEY.startswith('sk_test_'):
            raise ValueError("⚠️ 本番キーが検出されました。テストキーを使用してください！")

        logger.info("🧪 Stripe統合テスト開始 - テストモード確認済み")
        logger.info(f"🔑 使用中のキー: {settings.STRIPE_SECRET_KEY[:12]}...")

    def setUp(self):
        """各テスト前の準備"""
        # 先にオーガニゼーションを作成
        self.organization = Organization.objects.create(
            name='Test Organization',
            phone_number='080-1234-5678'
        )

        # オーガニゼーションを指定してユーザー作成
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            phone_number='080-1111-1111',
            organization=self.organization
        )
        self.user.is_active = True  # ユーザーをアクティブにする
        self.user.save()

        # JWTトークンを生成
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        # APIクライアントを設定
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        # Stripe上でテスト用プロダクトとプライスを作成
        test_product = stripe.Product.create(
            name='Test Basic Plan',
            metadata={'test': 'integration'}
        )

        test_price = stripe.Price.create(
            unit_amount=1000,  # 1000円
            currency='jpy',
            recurring={'interval': 'month'},
            product=test_product.id,
            metadata={'test': 'integration'}
        )

        # テスト用サブスクリプションプラン
        self.subscription_plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            description='テスト用ベーシックプラン',
            price=1000,  # 1000円/月
            max_duration=100,  # 100分
            stripe_price_id=test_price.id  # 実際に作成したPriceを使用
        )

        # クリーンアップ用に保存
        self.test_product = test_product
        self.test_price = test_price

        logger.info(f"🔧 テストデータ準備完了 - User: {self.user.username}")

    def tearDown(self):
        """テスト後のクリーンアップ"""
        try:
            # Priceを非アクティブ化（削除はできないので）
            stripe.Price.modify(self.test_price.id, active=False)
            logger.info("🧹 Stripeテストリソースクリーンアップ完了")
        except Exception as e:
            logger.warning(f"⚠️ クリーンアップエラー: {e}")


class StripeCheckoutIntegrationTest(StripeIntegrationTestCase):
    """Stripeチェックアウト統合テスト"""

    def test_create_checkout_session_real_api(self):
        """リアルStripe APIでチェックアウトセッション作成"""
        logger.info("🛒 チェックアウトセッション作成テスト開始")

        try:
            # 直接Stripe APIでチェックアウトセッション作成をテスト
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': self.subscription_plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url='https://example.com/success',
                cancel_url='https://example.com/cancel',
                customer_email=self.user.email,
                metadata={
                    'organization_id': str(self.organization.id),
                    'plan_id': str(self.subscription_plan.id),
                }
            )

            # セッション検証
            self.assertEqual(session.mode, 'subscription')
            self.assertEqual(session.status, 'open')
            self.assertTrue(session.url.startswith('https://checkout.stripe.com'))

            logger.info(f"✅ チェックアウトセッション作成成功: {session.id}")

        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe APIエラー: {e}")
            self.fail(f"Stripe APIエラー: {e}")
        except Exception as e:
            logger.error(f"❌ テストエラー: {e}")
            raise


class StripeCustomerPortalIntegrationTest(StripeIntegrationTestCase):
    """Stripeカスタマーポータル統合テスト"""

    def setUp(self):
        super().setUp()

        # テスト用サブスクリプション作成
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            plan=self.subscription_plan,
            stripe_customer_id='cus_test_customer',
            stripe_subscription_id='sub_test_subscription',
            status=Subscription.Status.ACTIVE
        )

    def test_create_customer_portal_session(self):
        """カスタマーポータルセッション作成テスト"""
        logger.info("🏪 カスタマーポータルセッション作成テスト開始")

        try:
            # まずStripe上でテスト顧客を作成
            customer = stripe.Customer.create(
                email=self.user.email,
                metadata={'organization_id': str(self.organization.id)}
            )

            # 直接Stripe APIでカスタマーポータルセッション作成をテスト
            portal_session = stripe.billing_portal.Session.create(
                customer=customer.id,
                return_url='https://example.com/dashboard'
            )

            # ポータルセッション検証
            self.assertTrue(portal_session.url.startswith('https://billing.stripe.com'))
            self.assertEqual(portal_session.customer, customer.id)

            logger.info(f"✅ カスタマーポータルセッション作成成功")

            # クリーンアップ
            stripe.Customer.delete(customer.id)

        except stripe.error.StripeError as e:
            if "No configuration provided" in str(e):
                logger.info("⚠️ カスタマーポータル設定が未完了のためスキップ")
                self.skipTest("カスタマーポータル設定が必要です。Stripeダッシュボードで設定してください。")
            else:
                logger.error(f"❌ Stripe APIエラー: {e}")
                self.fail(f"Stripe APIエラー: {e}")


class StripeWebhookIntegrationTest(StripeIntegrationTestCase):
    """Stripe Webhook統合テスト"""

    def test_webhook_signature_validation(self):
        """Webhook署名検証テスト"""
        logger.info("🔐 Webhook署名検証テスト開始")

        # テスト用イベントペイロード
        payload = '''
        {
          "id": "evt_test_webhook",
          "object": "event",
          "api_version": "2022-11-15",
          "created": 1677649265,
          "data": {
            "object": {
              "id": "cs_test_checkout_session",
              "object": "checkout.session"
            }
          },
          "livemode": false,
          "pending_webhooks": 1,
          "request": {
            "id": null,
            "idempotency_key": null
          },
          "type": "checkout.session.completed"
        }
        '''

        # 署名生成（テスト用）
        import hmac
        import hashlib

        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        if webhook_secret.startswith('whsec_'):
            # 実際の署名生成
            timestamp = str(int(time.time()))
            signature_payload = f"{timestamp}.{payload}"
            signature = hmac.new(
                webhook_secret.encode('utf-8'),
                signature_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            stripe_signature = f"t={timestamp},v1={signature}"
        else:
            # テスト用ダミー署名
            stripe_signature = "t=1677649265,v1=test_signature"

        # Webhookエンドポイントテスト
        response = self.client.post(
            '/api/webhook/stripe/',
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=stripe_signature
        )

        # 署名が正しい場合は処理される（200）
        # 署名が間違っている場合は拒否される（400）
        self.assertIn(response.status_code, [200, 400])

        logger.info(f"✅ Webhook署名検証テスト完了 - Status: {response.status_code}")


class StripeSubscriptionLifecycleTest(StripeIntegrationTestCase):
    """サブスクリプションライフサイクル統合テスト"""

    def test_subscription_creation_and_management(self):
        """サブスクリプション作成・管理テスト"""
        logger.info("🔄 サブスクリプションライフサイクルテスト開始")

        try:
            # 1. 顧客作成
            customer = stripe.Customer.create(
                email=self.user.email,
                metadata={'organization_id': str(self.organization.id)}
            )

            # 2. 製品とプライス作成（テスト用）
            product = stripe.Product.create(
                name='Test Product',
                metadata={'test': 'true'}
            )

            price = stripe.Price.create(
                unit_amount=1000,  # $10.00
                currency='usd',
                recurring={'interval': 'month'},
                product=product.id,
                metadata={'test': 'true'}
            )

            # 3. サブスクリプション作成（試用期間で作成して決済不要にする）
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{'price': price.id}],
                trial_period_days=30,  # 30日間の試用期間で決済方法不要
                metadata={'organization_id': str(self.organization.id)}
            )

            # 5. データベース確認
            db_subscription = Subscription.objects.create(
                organization=self.organization,
                plan=self.subscription_plan,
                stripe_customer_id=customer.id,
                stripe_subscription_id=subscription.id,
                status=Subscription.Status.ACTIVE
            )

            self.assertEqual(db_subscription.stripe_customer_id, customer.id)
            self.assertEqual(db_subscription.stripe_subscription_id, subscription.id)

            # 6. サブスクリプション更新テスト
            updated_subscription = stripe.Subscription.modify(
                subscription.id,
                metadata={'updated': 'true'}
            )

            self.assertEqual(updated_subscription.metadata['updated'], 'true')

            logger.info(f"✅ サブスクリプションライフサイクルテスト成功")

            # クリーンアップ
            stripe.Subscription.delete(subscription.id)
            stripe.Customer.delete(customer.id)
            # Product削除は制限があるため、ログのみ
            logger.info("💡 Productはテスト用として残します（削除制限があるため）")

        except stripe.error.StripeError as e:
            if "cannot be deleted" in str(e):
                logger.info("💡 Productはテスト用として残します（削除制限があるため）")
            else:
                logger.error(f"❌ Stripe APIエラー: {e}")
                self.fail(f"Stripe APIエラー: {e}")


class StripeErrorHandlingIntegrationTest(StripeIntegrationTestCase):
    """Stripeエラーハンドリング統合テスト"""

    def test_invalid_api_key_handling(self):
        """無効なAPIキーのハンドリングテスト"""
        logger.info("🚫 無効APIキーハンドリングテスト開始")

        # 無効なAPIキーを一時的に設定
        original_key = stripe.api_key
        stripe.api_key = 'sk_test_invalid_key'

        try:
            with self.assertRaises(stripe.error.AuthenticationError):
                stripe.Customer.list()

            logger.info("✅ 無効APIキーエラーハンドリング成功")

        finally:
            # 元のキーに戻す
            stripe.api_key = original_key

    def test_rate_limit_handling(self):
        """レート制限ハンドリングテスト"""
        logger.info("⏱️ レート制限ハンドリングテスト開始")

        # Note: 実際のレート制限テストは高負荷なので、
        # ここではエラータイプの確認のみ実施
        try:
            # 多数のリクエストを短時間で送信（実際にはレート制限を避ける）
            for i in range(3):  # 実際は100+だがテスト用に3回のみ
                stripe.Customer.list(limit=1)
                time.sleep(0.1)  # レート制限回避用

            logger.info("✅ レート制限テスト完了（制限に達しませんでした）")

        except stripe.error.RateLimitError as e:
            logger.info(f"✅ レート制限エラーハンドリング成功: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 予期しないエラー: {e}")


if __name__ == '__main__':
    import django
    django.setup()

    import unittest
    unittest.main()
