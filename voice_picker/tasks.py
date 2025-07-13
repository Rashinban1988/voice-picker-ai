import os
import tempfile
import logging
from celery import shared_task
from django.conf import settings
from .models import UploadedFile, Transcription
from .views import transcribe_and_save

processing_logger = logging.getLogger('processing')

@shared_task(bind=True)
def transcribe_and_save_async(self, file_path, uploaded_file_id):
    """
    音声ファイルの文字起こしを非同期で実行するCeleryタスク

    Args:
        file_path (str): 音声ファイルのパス
        uploaded_file_id (int): UploadedFileのID

    Returns:
        dict: 実行結果
    """
    try:
        processing_logger.info(f"Starting async transcription for file {file_path}, uploaded_file_id: {uploaded_file_id}")

        # UploadedFileの状態を処理中に更新
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            uploaded_file.status = UploadedFile.Status.PROCESSING
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            processing_logger.error(f"UploadedFile with id {uploaded_file_id} not found")
            return {"success": False, "error": "UploadedFile not found"}

        # 文字起こし実行
        success = transcribe_and_save(file_path, uploaded_file_id)

        if success:
            # 成功時はステータスを完了に更新
            uploaded_file.status = UploadedFile.Status.COMPLETED
            uploaded_file.save()
            processing_logger.info(f"Transcription completed successfully for uploaded_file_id: {uploaded_file_id}")
            return {"success": True, "uploaded_file_id": uploaded_file_id}
        else:
            # 失敗時はステータスをエラーに更新
            uploaded_file.status = UploadedFile.Status.ERROR
            uploaded_file.save()
            processing_logger.error(f"Transcription failed for uploaded_file_id: {uploaded_file_id}")
            return {"success": False, "error": "Transcription failed"}

    except Exception as e:
        processing_logger.error(f"Error in async transcription task: {e}")

        # エラー時もステータスを更新
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            uploaded_file.status = UploadedFile.Status.ERROR
            uploaded_file.save()
        except UploadedFile.DoesNotExist:
            pass

        # Celeryの自動リトライ機能を使用
        raise self.retry(exc=e, countdown=60, max_retries=3)
