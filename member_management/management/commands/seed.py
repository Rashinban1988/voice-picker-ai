# member_management/management/commands/seed.py
from django.core.management.base import BaseCommand
from member_management.models.user import User
from member_management.models.organization import Organization

class Command(BaseCommand):
    help = 'Seed the database with initial data'

    def handle(self, *args, **kwargs):
        # 組織を作成
        org = Organization.objects.create(name='Leadeas', phone_number='08069327260')

        # スーパーユーザーを作成
        user = User.objects.create(
            username='admin',
            email='rashinban1988@gmail.com',
            password='otomamay',
            organization=org,
            is_superuser=True,  # スーパーユーザーに設定
            is_staff=True,      # スタッフに設定
            is_active=True,     # アクティブに設定
            is_admin=True       # 管理者フラグを設定（必要に応じて）
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database'))