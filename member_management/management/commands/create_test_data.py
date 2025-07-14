from django.core.management.base import BaseCommand
from member_management.models import SubscriptionPlan, Organization, Subscription
from django.utils import timezone
from datetime import timedelta
import os

class Command(BaseCommand):
    help = 'テスト用のプランとサブスクリプションを作成'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-name',
            type=str,
            default='TestOrg',
            help='対象組織名（デフォルト: TestOrg）'
        )

    def handle(self, *args, **options):
        org_name = options['org_name']

        # テストモードの確認
        if os.getenv('TESTING_MODE') != 'true':
            self.stdout.write(
                self.style.WARNING('テストモードが有効化されていません。.envでTESTING_MODE=trueを設定してください。')
            )
            return

        # テスト用プランを作成または取得
        test_plan, created = SubscriptionPlan.objects.get_or_create(
            name='テスト用無制限プラン',
            defaults={
                'price': 0,
                'max_duration': 999999,  # 無制限
                'description': 'テスト・開発用の無制限プラン',
                'is_active': True
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'テスト用プランを作成しました: {test_plan.name}')
            )
        else:
            self.stdout.write(f'既存のテスト用プランを使用: {test_plan.name}')

        # 組織を検索
        try:
            organization = Organization.objects.get(name=org_name)
        except Organization.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'組織 "{org_name}" が見つかりません。')
            )
            return

        # 既存のサブスクリプションを確認
        existing_subscription = organization.get_subscription()
        if existing_subscription:
            # 既存のサブスクリプションを無制限プランに更新
            existing_subscription.plan = test_plan
            existing_subscription.current_period_start = timezone.now()
            existing_subscription.current_period_end = timezone.now() + timedelta(days=365)  # 1年間有効
            existing_subscription.status = Subscription.Status.ACTIVE
            existing_subscription.save()

            self.stdout.write(
                self.style.SUCCESS(f'組織 "{org_name}" のサブスクリプションをテスト用プランに更新しました')
            )
        else:
            # 新しいサブスクリプションを作成
            subscription = Subscription.objects.create(
                organization=organization,
                plan=test_plan,
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=365),  # 1年間有効
                status=Subscription.Status.ACTIVE
            )

            self.stdout.write(
                self.style.SUCCESS(f'組織 "{org_name}" にテスト用サブスクリプションを作成しました')
            )

        # 現在の状況を表示
        self.stdout.write('\n=== 現在の設定 ===')
        self.stdout.write(f'組織: {organization.name}')
        self.stdout.write(f'プラン: {test_plan.name}')
        self.stdout.write(f'最大時間: {test_plan.max_duration}分')
        self.stdout.write(f'テストモード: {os.getenv("TESTING_MODE")}')
        self.stdout.write(f'無制限アップロード: {os.getenv("TEST_UNLIMITED_UPLOAD")}')

        self.stdout.write('\n✅ テスト準備完了！制限なしでファイルアップロードが可能です。')
