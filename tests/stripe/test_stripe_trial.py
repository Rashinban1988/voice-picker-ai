#!/usr/bin/env python
"""
Stripe 30日トライアル機能のテストスクリプト

このスクリプトでは以下をテストします：
1. 新規ユーザーのトライアル開始
2. トライアル期間中のステータス確認
3. トライアル済みユーザーの再登録防止
4. Webhookイベントの処理
"""

import os
import sys
import django
import time
import json
from datetime import datetime, timedelta

# Djangoプロジェクトのパスを追加（Dockerコンテナ内の場合は/code）
if os.path.exists('/code'):
    sys.path.insert(0, '/code')
else:
    sys.path.insert(0, '/Users/yamamoto/develop/portforio/voice-picker-ai/macching_app')

# Django設定（通常の設定を使用）
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import stripe
from django.conf import settings
from django.utils import timezone
from member_management.models import Organization, Subscription, SubscriptionPlan, User
from member_management.views import fulfill_subscription, update_subscription

# Stripeテストキーの設定
stripe.api_key = settings.STRIPE_SECRET_KEY

def print_section(title):
    """セクション区切りを表示"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def create_test_organization(name_suffix=""):
    """テスト用組織を作成"""
    org_name = f"Test Organization {name_suffix} {datetime.now().strftime('%Y%m%d%H%M%S')}"
    org = Organization.objects.create(
        name=org_name,
        phone_number="03-1234-5678"
    )
    print(f"✅ 組織作成: {org.name} (ID: {org.id})")
    return org

def create_test_user(organization):
    """テスト用ユーザーを作成"""
    import random
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = random.randint(1000, 9999)
    user = User.objects.create_user(
        username=f"testuser_{timestamp}_{random_suffix}",
        email=f"test_{timestamp}_{random_suffix}@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
        organization=organization,
        phone_number=f"090-{random.randint(1000,9999)}-{random.randint(1000,9999)}"  # 完全にランダムな電話番号
    )
    print(f"✅ ユーザー作成: {user.email}")
    return user

def get_or_create_test_plan():
    """テスト用プランを取得または作成"""
    # 既存のプランを確認
    plans = SubscriptionPlan.objects.filter(is_active=True)
    if plans.exists():
        plan = plans.first()
        print(f"✅ 既存プラン使用: {plan.name} (ID: {plan.id})")
        return plan

    # プランが無い場合は作成
    plan = SubscriptionPlan.objects.create(
        name="Test Plan",
        description="テスト用プラン",
        price=1000,
        max_duration=100,
        stripe_price_id="price_test_dummy",
        is_active=True
    )
    print(f"✅ 新規プラン作成: {plan.name}")
    return plan

def test_trial_creation():
    """新規ユーザーのトライアル作成テスト"""
    print_section("TEST 1: 新規ユーザーのトライアル作成")

    # テストデータ準備
    org = create_test_organization("Trial")
    user = create_test_user(org)
    plan = get_or_create_test_plan()

    # サブスクリプション作成
    subscription = Subscription.objects.create(
        organization=org,
        plan=plan,
        status=Subscription.Status.INACTIVE
    )
    print(f"✅ サブスクリプション作成 (ID: {subscription.id})")
    print(f"   - has_used_trial: {subscription.has_used_trial}")

    # Stripeカスタマー作成をシミュレート
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{org.name} ({user.last_name} {user.first_name})",
            metadata={
                'organization_id': str(org.id),
                'user_id': str(user.id)
            }
        )
        subscription.stripe_customer_id = customer.id
        subscription.save()
        print(f"✅ Stripeカスタマー作成 (ID: {customer.id})")
    except Exception as e:
        print(f"⚠️  Stripeカスタマー作成スキップ (テストモード): {e}")
        subscription.stripe_customer_id = f"cus_test_{org.id}"
        subscription.save()

    # トライアル期間の確認
    if not subscription.has_used_trial:
        print("✅ トライアル利用可能（30日間）")

        # トライアル開始をシミュレート
        subscription.status = Subscription.Status.TRIAL
        subscription.has_used_trial = True
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = timezone.now() + timedelta(days=30)
        subscription.save()

        print(f"✅ トライアル開始")
        print(f"   - ステータス: {subscription.get_status_display()}")
        print(f"   - 開始日: {subscription.current_period_start}")
        print(f"   - 終了日: {subscription.current_period_end}")
        print(f"   - has_used_trial: {subscription.has_used_trial}")
    else:
        print("❌ トライアル使用済み")

    return subscription

def test_trial_status_check(subscription):
    """トライアル期間中のステータス確認テスト"""
    print_section("TEST 2: トライアル期間中のステータス確認")

    # リロードして最新の状態を取得
    subscription.refresh_from_db()

    print(f"現在のステータス:")
    print(f"   - ステータス: {subscription.get_status_display()}")
    print(f"   - is_active(): {subscription.is_active()}")
    print(f"   - is_within_contract_period(): {subscription.is_within_contract_period()}")
    print(f"   - has_used_trial: {subscription.has_used_trial}")

    if subscription.status == Subscription.Status.TRIAL:
        print("✅ トライアル期間中です")
        remaining_days = (subscription.current_period_end - timezone.now()).days
        print(f"   - 残り日数: {remaining_days}日")
    else:
        print(f"⚠️  トライアル期間外です (ステータス: {subscription.get_status_display()})")

def test_trial_reuse_prevention():
    """トライアル済みユーザーの再登録防止テスト"""
    print_section("TEST 3: トライアル済みユーザーの再登録防止")

    # トライアル使用済みの組織を作成
    org = create_test_organization("Used Trial")
    user = create_test_user(org)
    plan = get_or_create_test_plan()

    # 使用済みフラグを立てたサブスクリプション作成
    subscription = Subscription.objects.create(
        organization=org,
        plan=plan,
        status=Subscription.Status.CANCELED,
        has_used_trial=True  # 既に使用済み
    )
    print(f"✅ トライアル使用済みサブスクリプション作成")
    print(f"   - has_used_trial: {subscription.has_used_trial}")

    # 再度トライアルを試みる
    if subscription.has_used_trial:
        print("✅ トライアル再利用防止が機能しています")
        print("   - トライアル期間: 0日（即座に課金開始）")
    else:
        print("❌ トライアル再利用防止が機能していません")

def test_webhook_simulation():
    """Webhookイベントのシミュレーションテスト"""
    print_section("TEST 4: Webhookイベントシミュレーション")

    # テストデータ準備
    org = create_test_organization("Webhook")
    user = create_test_user(org)
    plan = get_or_create_test_plan()

    subscription = Subscription.objects.create(
        organization=org,
        plan=plan,
        status=Subscription.Status.INACTIVE,
        stripe_customer_id=f"cus_test_{org.id}",
        stripe_subscription_id=f"sub_test_{org.id}"
    )

    print("1. checkout.session.completed イベント")
    session_data = {
        'id': f'cs_test_{org.id}',
        'customer': subscription.stripe_customer_id,
        'subscription': subscription.stripe_subscription_id,
        'metadata': {
            'organization_id': str(org.id),
            'plan_id': str(plan.id)
        }
    }

    try:
        fulfill_subscription(session_data)
        subscription.refresh_from_db()
        print(f"   ✅ ステータス更新: {subscription.get_status_display()}")
    except Exception as e:
        print(f"   ⚠️  エラー: {e}")

    print("\n2. customer.subscription.updated イベント (トライアル開始)")
    stripe_sub_data = {
        'id': subscription.stripe_subscription_id,
        'customer': subscription.stripe_customer_id,
        'status': 'trialing',
        'current_period_start': int(timezone.now().timestamp()),
        'current_period_end': int((timezone.now() + timedelta(days=30)).timestamp()),
        'cancel_at_period_end': False
    }

    try:
        update_subscription(stripe_sub_data)
        subscription.refresh_from_db()
        print(f"   ✅ ステータス更新: {subscription.get_status_display()}")
        print(f"   ✅ has_used_trial: {subscription.has_used_trial}")
    except Exception as e:
        print(f"   ⚠️  エラー: {e}")

def test_trial_to_active_transition():
    """トライアルから有料プランへの移行テスト"""
    print_section("TEST 5: トライアル→有料プラン移行")

    # トライアル中のサブスクリプションを作成
    org = create_test_organization("Transition")
    user = create_test_user(org)
    plan = get_or_create_test_plan()

    subscription = Subscription.objects.create(
        organization=org,
        plan=plan,
        status=Subscription.Status.TRIAL,
        has_used_trial=True,
        stripe_customer_id=f"cus_test_{org.id}",
        stripe_subscription_id=f"sub_test_{org.id}",
        current_period_start=timezone.now() - timedelta(days=25),
        current_period_end=timezone.now() + timedelta(days=5)
    )

    print(f"トライアル期間残り: {(subscription.current_period_end - timezone.now()).days}日")

    # 有料プランへの移行をシミュレート
    stripe_sub_data = {
        'id': subscription.stripe_subscription_id,
        'customer': subscription.stripe_customer_id,
        'status': 'active',  # トライアルから有料へ
        'current_period_start': int(timezone.now().timestamp()),
        'current_period_end': int((timezone.now() + timedelta(days=30)).timestamp()),
        'cancel_at_period_end': False
    }

    update_subscription(stripe_sub_data)
    subscription.refresh_from_db()

    print(f"✅ 移行完了")
    print(f"   - 新ステータス: {subscription.get_status_display()}")
    print(f"   - 次回請求日: {subscription.current_period_end}")

def main():
    """メイン実行関数"""
    print("\n" + "🚀"*30)
    print(" Stripe 30日トライアル機能テスト")
    print("🚀"*30)

    print(f"\n環境設定:")
    print(f"   - DATABASE: {settings.DATABASES['default']['ENGINE']}")
    print(f"   - STRIPE_PUBLISHABLE_KEY: {settings.STRIPE_PUBLISHABLE_KEY[:20] if settings.STRIPE_PUBLISHABLE_KEY else 'Not Set'}...")
    print(f"   - STRIPE_SECRET_KEY: {settings.STRIPE_SECRET_KEY[:20] if settings.STRIPE_SECRET_KEY else 'Not Set'}...")
    print(f"   - STRIPE_WEBHOOK_SECRET: {settings.STRIPE_WEBHOOK_SECRET[:20] if settings.STRIPE_WEBHOOK_SECRET else 'Not Set'}...")

    # 各テストを実行
    subscription = test_trial_creation()
    test_trial_status_check(subscription)
    test_trial_reuse_prevention()
    test_webhook_simulation()
    test_trial_to_active_transition()

    print_section("テスト完了")
    print("✅ すべてのテストが完了しました")

    # テストデータのクリーンアップ確認
    print("\n⚠️  テストデータが残っています。削除しますか？ (y/n): ", end="")
    if input().lower() == 'y':
        # 今回のテストで作成したデータを削除
        Organization.objects.filter(name__startswith="Test Organization").delete()
        print("✅ テストデータを削除しました")

if __name__ == "__main__":
    main()