from django.core.management.base import BaseCommand
from django.db import transaction
from voice_picker.models import UploadedFile
from voice_picker.views import transcribe_and_save, text_generation_save
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '音声ファイルを文字起こしする'

    @transaction.atomic
    def handle(self, *args, **options):
        # transcriptionを持っていないuploaded_fileを取得
        uploaded_files = UploadedFile.objects.filter(transcription__isnull=True, status=0).select_for_update()

        if not uploaded_files.exists():
            logger.info('文字起こしするファイルがありませんでした。')
            return

        for uploaded_file in uploaded_files:
            try:
                uploaded_file.status = 1
                uploaded_file.save()

                file_path = uploaded_file.file.path
                uploaded_file_id = uploaded_file.id

                transcribe_and_save_result = transcribe_and_save(file_path, uploaded_file_id)
                if not transcribe_and_save_result:
                    uploaded_file.status = 0
                    uploaded_file.save()
                    continue

                uploaded_file = text_generation_save(uploaded_file)
                if not uploaded_file:
                    uploaded_file.status = 3 # 要約失敗
                    uploaded_file.save()
                    continue

                uploaded_file.status = 2
                uploaded_file.save()

                logger.info(f'正常に文字起こしが完了しました。File ID: {uploaded_file_id}')
            except Exception as e:
                uploaded_file.status = 0
                uploaded_file.save()
                logger.exception(f"文字起こしでエラーが発生しました。File ID: {uploaded_file_id}")
                logger.error(f'文字起こしでエラーが発生しました: {e}')

        logger.info('全ファイルの文字起こし処理が完了しました。')