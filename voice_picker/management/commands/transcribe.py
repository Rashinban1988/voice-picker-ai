from django.core.management.base import BaseCommand
from django.db import transaction
from voice_picker.models import UploadedFile
from voice_picker.views import transcribe_and_save, text_generation_save
from voice_picker.models.uploaded_file import Status
import logging

logger = logging.getLogger('processing')

class Command(BaseCommand):
    help = '音声ファイルを文字起こしする'

    @transaction.atomic
    def handle(self, *args, **options):
        logger.info('文字起こし処理を開始します。')
        # transcriptionを持っていないuploaded_fileを取得
        uploaded_files = UploadedFile.objects.filter(transcription__isnull=True, status=Status.UNPROCESSED).select_for_update()

        if not uploaded_files.exists():
            logger.info('文字起こしするファイルがありませんでした。')
            return

        for uploaded_file in uploaded_files:
            try:
                uploaded_file.status = Status.IN_PROGRESS
                uploaded_file.save()

                file_path = uploaded_file.file.path
                uploaded_file_id = uploaded_file.id

                transcribe_and_save_result = transcribe_and_save(file_path, uploaded_file_id)
                if not transcribe_and_save_result:
                    uploaded_file.status = Status.UNPROCESSED
                    uploaded_file.save()
                    continue

                # uploaded_file = text_generation_save(uploaded_file)
                # logger.info(f"text_generation_saveの戻り値: {uploaded_file}")
                # if not isinstance(uploaded_file, UploadedFile):
                #     uploaded_file.status = Status.ERROR
                #     uploaded_file.save()
                #     logger.error("text_generation_saveが無効な戻り値を返しました。")
                #     continue

                uploaded_file.status = Status.PROCESSED
                uploaded_file.save()

                logger.info(f'正常に文字起こしが完了しました。File ID: {uploaded_file_id}')
            except Exception as e:
                uploaded_file.status = Status.UNPROCESSED
                uploaded_file.save()
                logger.exception(f"文字起こしでエラーが発生しました。File ID: {uploaded_file_id}")
                logger.error(f'文字起こしでエラーが発生しました: {e}')

        logger.info('全ファイルの文字起こし処理が完了しました。')