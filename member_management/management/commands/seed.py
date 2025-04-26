# member_management/management/commands/seed.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from member_management.models.user import User
from member_management.models.organization import Organization
from member_management.models.subscription import SubscriptionPlan, Subscription

class Command(BaseCommand):
    help = 'Seed the database with initial data'

    def handle(self, *args, **kwargs):
        # 組織を作成
        org = Organization.objects.create(name='TestCompany', phone_number='08069327255')

        # スーパーユーザーを作成
        user = User.objects.create(
            username='test@test.com',
            email='test@test.com',
            password='password',
            organization=org,
            is_superuser=True,  # スーパーユーザーに設定
            is_staff=True,      # スタッフに設定
            is_active=True,     # アクティブに設定
            is_admin=True,      # 管理者フラグを設定（必要に応じて）
            email_verified=True,
        )

        # サブスクリプションプランを作成
        basic_plan = SubscriptionPlan.objects.create(
            name='ベーシックプラン',
            description='基本的な機能が利用可能な標準プラン',
            price=980,
            max_duration=60,
            stripe_price_id='price_test_basic',
            is_active=True
        )

        premium_plan = SubscriptionPlan.objects.create(
            name='プレミアムプラン',
            description='すべての機能が利用可能な上級プラン',
            price=1980,
            max_duration=120,
            stripe_price_id='price_test_premium',
            is_active=True
        )

        # サブスクリプションを作成
        subscription = Subscription.objects.create(
            organization=org,
            plan=basic_plan,
            status=1,  # 有効
            stripe_customer_id='cus_test_123',
            stripe_subscription_id='sub_test_123',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
            cancel_at_period_end=False
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database'))