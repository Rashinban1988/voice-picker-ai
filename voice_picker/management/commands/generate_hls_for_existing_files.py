import os
from django.core.management.base import BaseCommand
from voice_picker.models import UploadedFile
from voice_picker.tasks import generate_hls_async


class Command(BaseCommand):
    help = '既存の動画ファイルに対してHLS生成処理を実行します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file-id',
            type=str,
            help='特定のファイルIDに対してのみHLS生成を実行'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='既にHLSパスが設定されているファイルも再処理'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の処理は行わず、対象ファイルのみを表示'
        )

    def handle(self, *args, **options):
        # 動画ファイルの拡張子
        video_extensions = ('.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm')

        # 対象ファイルのフィルタリング
        queryset = UploadedFile.objects.filter(exist=True)

        if options['file_id']:
            queryset = queryset.filter(id=options['file_id'])

        if not options['force']:
            # HLSパスが設定されていないファイルのみ
            queryset = queryset.filter(hls_playlist_path__isnull=True)

        # 動画ファイルのみに絞り込み
        video_files = []
        for uploaded_file in queryset:
            if uploaded_file.file.name.lower().endswith(video_extensions):
                video_files.append(uploaded_file)

        if not video_files:
            self.stdout.write(
                self.style.WARNING('対象となる動画ファイルが見つかりませんでした。')
            )
            return

        self.stdout.write(
            f'対象ファイル数: {len(video_files)}件'
        )

        for uploaded_file in video_files:
            self.stdout.write(
                f'ファイル: {uploaded_file.file.name} (ID: {uploaded_file.id})'
            )

            if options['dry_run']:
                continue

            try:
                # HLS生成タスクをキューに追加
                generate_hls_async.delay(str(uploaded_file.id))
                self.stdout.write(
                    self.style.SUCCESS(f'✓ HLS生成タスクをキューに追加しました: {uploaded_file.file.name}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ エラーが発生しました: {uploaded_file.file.name} - {str(e)}')
                )

        if not options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(f'\n合計 {len(video_files)} 件のファイルをHLS生成キューに追加しました。')
            )
            self.stdout.write(
                'Celeryワーカーでバックグラウンド処理が開始されます。'
            )
