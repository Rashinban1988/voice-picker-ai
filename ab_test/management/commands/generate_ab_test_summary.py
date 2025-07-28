"""
A/Bテストの日次サマリーを生成するコマンド
crontabで毎日実行することを想定
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone
from datetime import datetime, timedelta
from ab_test.models import ABTestEvent, ABTestSession, ABTestSummary


class Command(BaseCommand):
    help = 'Generate daily A/B test summary'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Target date (YYYY-MM-DD). Defaults to yesterday.',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days to process (default: 1)',
        )

    def handle(self, *args, **options):
        target_date = options.get('date')
        days = options.get('days', 1)
        
        if target_date:
            try:
                start_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD.')
                )
                return
        else:
            # デフォルトは昨日
            start_date = (timezone.now() - timedelta(days=1)).date()
        
        self.stdout.write(f'Generating summary for {days} days starting from {start_date}')
        
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            self.generate_summary_for_date(current_date)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated summaries for {days} days')
        )

    def generate_summary_for_date(self, target_date):
        """指定日のサマリーを生成"""
        self.stdout.write(f'Processing {target_date}...')
        
        for variant in ['A', 'B']:
            # その日のイベントを取得
            events = ABTestEvent.objects.filter(
                variant=variant,
                created_at__date=target_date
            )
            
            # その日に初回訪問したセッションを取得
            sessions = ABTestSession.objects.filter(
                variant=variant,
                first_visit__date=target_date
            )
            
            # 各種カウント
            page_views = events.filter(event='page_view').count()
            register_clicks = events.filter(event='register_click').count()
            login_clicks = events.filter(event='login_click').count()
            conversions = events.filter(event='conversion').count()
            unique_sessions = sessions.count()
            
            # コンバージョン率計算
            conversion_rate = conversions / unique_sessions if unique_sessions > 0 else 0
            
            # サマリーを更新または作成
            summary, created = ABTestSummary.objects.update_or_create(
                date=target_date,
                variant=variant,
                defaults={
                    'page_views': page_views,
                    'register_clicks': register_clicks,
                    'login_clicks': login_clicks,
                    'conversions': conversions,
                    'unique_sessions': unique_sessions,
                    'conversion_rate': conversion_rate,
                }
            )
            
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                f'  {action} summary for variant {variant}: '
                f'{page_views} views, {conversions} conversions, '
                f'{conversion_rate:.4f} rate'
            )