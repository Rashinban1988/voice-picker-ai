from django.core.management.base import BaseCommand
from django.db import transaction
from voice_picker.models import UploadedFile
from voice_picker.views import transcribe_and_save, text_generation_save
from voice_picker.models.uploaded_file import Status
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '音声ファイルを文字起こしする'

    def handle(self, *args, **options):
        uploaded_file_ids = list(UploadedFile.objects.filter(
            transcription__isnull=True, 
            status=Status.UNPROCESSED
        ).values_list('id', flat=True))

        if not uploaded_file_ids:
            logger.info('文字起こしするファイルがありませんでした。')
            return

        for uploaded_file_id in uploaded_file_ids:
            try:
                try:
                    uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
                    uploaded_file.status = Status.IN_PROGRESS
                    uploaded_file.save()
                except UploadedFile.DoesNotExist:
                    logger.error(f"ファイルが見つかりませんでした。File ID: {uploaded_file_id}")
                    continue

                file_path = uploaded_file.file.path

                transcribe_and_save_result = transcribe_and_save(file_path, uploaded_file_id)
                if not transcribe_and_save_result:
                    uploaded_file.status = Status.UNPROCESSED
                    uploaded_file.save()
                    continue

                result_uploaded_file = text_generation_save(uploaded_file)
                logger.info(f"text_generation_saveの戻り値: {result_uploaded_file}")
                if not isinstance(result_uploaded_file, UploadedFile):
                    uploaded_file.status = Status.ERROR
                    uploaded_file.save()
                    logger.error("text_generation_saveが無効な戻り値を返しました。")
                    continue

                uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
                uploaded_file.status = Status.PROCESSED
                uploaded_file.save()

                logger.info(f'正常に文字起こしが完了しました。File ID: {uploaded_file_id}')
            except Exception as e:
                try:
                    uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
                    uploaded_file.status = Status.UNPROCESSED
                    uploaded_file.save()
                except UploadedFile.DoesNotExist:
                    pass
                logger.exception(f"文字起こしでエラーが発生しました。File ID: {uploaded_file_id}")
                logger.error(f'文字起こしでエラーが発生しました: {e}')

        logger.info('全ファイルの文字起こし処理が完了しました。')
