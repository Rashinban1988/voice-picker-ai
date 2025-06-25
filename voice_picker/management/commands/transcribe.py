from django.core.management.base import BaseCommand
from django.db import transaction
from voice_picker.models import UploadedFile, Environment
from voice_picker.views import transcribe_and_save, text_generation_save, transcribe_without_diarization
from voice_picker.models.uploaded_file import Status
import logging
import requests
import os

processing_logger = logging.getLogger('processing')

class Command(BaseCommand):
    help = '音声ファイルを文字起こしする'

    def handle(self, *args, **options):
        # ngrokのエンドポイントを取得
        # try:
        #     environment = Environment.objects.get(code='ngrok')
        #     ngrok_endpoint = environment.value
        #     if not ngrok_endpoint:
        #         processing_logger.error('ngrokのエンドポイントが設定されていません。')
        #         return
        # except Environment.DoesNotExist:
        #     processing_logger.error('ngrokのエンドポイントが設定されていません。')
        #     return

        unprocessed_files = UploadedFile.objects.filter(
            transcription__isnull=True,
            status=Status.UNPROCESSED
        )

        if not unprocessed_files.exists():
            processing_logger.info('文字起こしするファイルがありませんでした。')
            return

        file_ids = list(unprocessed_files.values_list('id', flat=True))
        UploadedFile.objects.filter(id__in=file_ids).update(status=Status.IN_PROGRESS)
        processing_logger.info(f'{len(file_ids)}件のファイルを処理中に設定しました。')

        for file_id in file_ids:
            try:
                try:
                    uploaded_file = UploadedFile.objects.get(id=file_id)
                except UploadedFile.DoesNotExist:
                    processing_logger.error(f"ファイルが見つかりませんでした。File ID: {file_id}")
                    continue

                file_path = uploaded_file.file.path

                organization = uploaded_file.organization

                if organization.is_free_user():
                    # 無料ユーザーの場合の処理
                    with transaction.atomic():
                        transcribe_result = transcribe_without_diarization(file_path, file_id, is_free_user=True)
                        if not transcribe_result:
                            UploadedFile.objects.filter(id=file_id).update(status=Status.UNPROCESSED)
                            processing_logger.error(f"文字起こしに失敗しました。File ID: {file_id}")
                            continue

                        result = text_generation_save(uploaded_file)
                        if not isinstance(result, UploadedFile):
                            raise Exception("テキスト生成に失敗しました")

                        UploadedFile.objects.filter(id=file_id).update(status=Status.PROCESSED)
                else:
                    # 有料会員の場合
                    with transaction.atomic():
                        # transcribe_google_colab(file_path, file_id)
                        transcribe_result = transcribe_without_diarization(file_path, file_id)
                        if not transcribe_result:
                            UploadedFile.objects.filter(id=file_id).update(status=Status.UNPROCESSED)
                            processing_logger.error(f"文字起こしに失敗しました。File ID: {file_id}")
                            continue

                        result = text_generation_save(uploaded_file)
                        if not isinstance(result, UploadedFile):
                            raise Exception("テキスト生成に失敗しました")

                        UploadedFile.objects.filter(id=file_id).update(status=Status.PROCESSED)

                processing_logger.info(f'正常に文字起こしが完了しました。File ID: {file_id}')

            except Exception as e:
                UploadedFile.objects.filter(id=file_id).update(status=Status.UNPROCESSED)
                processing_logger.exception(f"文字起こしでエラーが発生しました。File ID: {file_id}")
                processing_logger.error(f'文字起こしでエラーが発生しました: {e}')

        processing_logger.info('全ファイルの文字起こし処理が完了しました。')

        def transcribe_google_colab(file_path, file_id):
            """Google Colabで文字起こしを行う"""
            try:
                # ファイルを読み込む
                with open(file_path, 'rb') as f:
                    files = {
                        'file': (os.path.basename(file_path), f, 'application/octet-stream')
                    }
                    data = {
                        'uploaded_file_id': str(uploaded_file.id)
                    }
                    response = requests.post(
                        f"{ngrok_endpoint}/process",
                        files=files,
                        data=data
                    )
                response.raise_for_status()
                processing_logger.info(f'ngrokエンドポイントへの通知が成功しました。File ID: {file_id}')
            except requests.exceptions.RequestException as e:
                processing_logger.error(f'ngrokエンドポイントへの通知に失敗しました。File ID: {file_id}, Error: {e}')
