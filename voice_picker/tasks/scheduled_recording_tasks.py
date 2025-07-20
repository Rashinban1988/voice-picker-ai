from celery import shared_task
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from ..models import ScheduledRecording, UploadedFile
from ..services.zoom_api_service import ZoomAPIService
import logging

logger = logging.getLogger(__name__)

# Status constants from UploadedFile.Status
STATUS_UNPROCESSED = 0
STATUS_PROCESSING = 1
STATUS_COMPLETED = 2
STATUS_ERROR = 3

@shared_task(bind=True, max_retries=3)
def schedule_recording_task(self, scheduled_recording_id):
    """
    予約録画のメインタスク
    指定時刻に録画を開始し、終了時刻に停止する
    """
    try:
        with transaction.atomic():
            recording = ScheduledRecording.objects.select_for_update().get(
                id=scheduled_recording_id
            )

            if recording.status != 'scheduled':
                logger.warning(f"Recording {recording.id} is not in scheduled status: {recording.status}")
                return

            # 録画開始時刻をチェック
            now = timezone.now()
            recording_window = recording.recording_window

            if now < recording_window['start']:
                # まだ開始時刻ではない場合、再スケジュール
                delay_seconds = int((recording_window['start'] - now).total_seconds())
                logger.info(f"Rescheduling recording {recording.id} in {delay_seconds} seconds")

                # 再スケジュール
                self.retry(countdown=delay_seconds)
                return

            if now > recording_window['end']:
                # 録画ウィンドウが過ぎている場合、失敗として処理
                recording.update_status('failed', 'Recording window has passed')
                return

            # 録画開始準備
            recording.update_status('preparing')

            # 録画開始
            result = start_scheduled_recording(recording)

            if result['success']:
                # 録画開始成功
                recording.update_status('recording')
                recording.zoom_session_id = result.get('session_id')
                recording.save()

                # 停止タスクをスケジュール
                stop_delay = int((recording_window['end'] - timezone.now()).total_seconds())
                if stop_delay > 0:
                    stop_scheduled_recording_task.apply_async(
                        args=[scheduled_recording_id],
                        countdown=stop_delay
                    )

                logger.info(f"Recording {recording.id} started successfully")
            else:
                # 録画開始失敗
                error_message = result.get('error', 'Unknown error')
                recording.update_status('failed', error_message)
                logger.error(f"Failed to start recording {recording.id}: {error_message}")

                # リトライ可能なエラーの場合、再試行
                if should_retry_error(error_message) and self.request.retries < self.max_retries:
                    logger.info(f"Retrying recording {recording.id} in 60 seconds")
                    self.retry(countdown=60)

    except ScheduledRecording.DoesNotExist:
        logger.error(f"Scheduled recording {scheduled_recording_id} not found")
    except Exception as e:
        logger.error(f"Error in schedule_recording_task: {e}")

        # 録画の状態を更新
        try:
            recording = ScheduledRecording.objects.get(id=scheduled_recording_id)
            recording.update_status('failed', str(e))
        except:
            pass

        # 予期しないエラーの場合もリトライ
        if self.request.retries < self.max_retries:
            self.retry(countdown=60)

@shared_task(bind=True)
def stop_scheduled_recording_task(self, scheduled_recording_id):
    """
    予約録画の停止タスク
    """
    try:
        with transaction.atomic():
            recording = ScheduledRecording.objects.select_for_update().get(
                id=scheduled_recording_id
            )

            if recording.status != 'recording':
                logger.warning(f"Recording {recording.id} is not in recording status: {recording.status}")
                return

            # 録画停止
            result = stop_scheduled_recording(recording)

            if result['success']:
                recording.update_status('completed')
                logger.info(f"Recording {recording.id} stopped successfully")
            else:
                error_message = result.get('error', 'Unknown error')
                recording.update_status('failed', error_message)
                logger.error(f"Failed to stop recording {recording.id}: {error_message}")

    except ScheduledRecording.DoesNotExist:
        logger.error(f"Scheduled recording {scheduled_recording_id} not found")
    except Exception as e:
        logger.error(f"Error in stop_scheduled_recording_task: {e}")

def start_scheduled_recording(recording):
    """
    予約録画を開始
    """
    try:
        from ..services.zoom_bot_service import ZoomBotService
        zoom_bot = ZoomBotService()

        # 録画開始
        result = zoom_bot.start_meeting_recording(
            meeting_url=recording.meeting_url,
            organization_id=recording.uploaded_file.organization_id,
            user_name=f"Voice Picker Bot (予約録画)"
        )

        if result['success']:
            # UploadedFileのsession_idを更新
            recording.uploaded_file.zoom_session_id = result.get('session_id')
            recording.uploaded_file.save()

        return result

    except Exception as e:
        logger.error(f"Error starting scheduled recording: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def stop_scheduled_recording(recording):
    """
    予約録画を停止
    """
    try:
        from ..services.zoom_bot_service import ZoomBotService
        zoom_bot = ZoomBotService()

        # 録画停止
        result = zoom_bot.stop_meeting_recording(
            uploaded_file_id=str(recording.uploaded_file.id)
        )

        return result

    except Exception as e:
        logger.error(f"Error stopping scheduled recording: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def should_retry_error(error_message):
    """
    リトライ可能なエラーかどうかを判定
    """
    retry_patterns = [
        'Connection failed',
        'Network error',
        'Timeout',
        'Meeting not started',
        'Bot server error',
        'Temporary error'
    ]

    return any(pattern in error_message for pattern in retry_patterns)

@shared_task
def cleanup_expired_scheduled_recordings():
    """
    期限切れの予約録画をクリーンアップ
    """
    try:
        # 24時間以上過去の予約録画を検索
        cutoff_time = timezone.now() - timedelta(hours=24)

        expired_recordings = ScheduledRecording.objects.filter(
            scheduled_start_time__lt=cutoff_time,
            status__in=['scheduled', 'preparing']
        )

        for recording in expired_recordings:
            logger.info(f"Cleaning up expired recording {recording.id}")
            recording.update_status('failed', 'Recording expired')

            # Celeryタスクもキャンセル
            if recording.celery_task_id:
                from celery import current_app
                current_app.control.revoke(recording.celery_task_id, terminate=True)

        logger.info(f"Cleaned up {expired_recordings.count()} expired recordings")

    except Exception as e:
        logger.error(f"Error in cleanup_expired_scheduled_recordings: {e}")

@shared_task
def monitor_scheduled_recordings():
    """
    予約録画の状態を監視し、必要に応じて修正
    """
    try:
        now = timezone.now()

        # 録画中だが時間が過ぎている録画を停止
        overdue_recordings = ScheduledRecording.objects.filter(
            status='recording',
            scheduled_end_time__lt=now - timedelta(minutes=30)  # 30分の余裕を見る
        )

        for recording in overdue_recordings:
            logger.warning(f"Stopping overdue recording {recording.id}")
            stop_scheduled_recording_task.delay(str(recording.id))

        # 開始時刻が過ぎているのに未開始の録画を失敗にする
        missed_recordings = ScheduledRecording.objects.filter(
            status='scheduled',
            scheduled_start_time__lt=now - timedelta(minutes=10)  # 10分の余裕を見る
        )

        for recording in missed_recordings:
            logger.warning(f"Marking missed recording {recording.id} as failed")
            recording.update_status('failed', 'Recording start time missed')

    except Exception as e:
        logger.error(f"Error in monitor_scheduled_recordings: {e}")

@shared_task
def create_scheduled_recording(meeting_url, organization_id, scheduled_start_time, user_options=None):
    """
    予約録画を作成
    """
    try:
        # Zoom API service
        zoom_api = ZoomAPIService()

        # 会議詳細情報を取得
        meeting_details = zoom_api.parse_meeting_url_advanced(meeting_url)

        # UploadedFileレコードを作成
        uploaded_file = UploadedFile.objects.create(
            organization_id=organization_id,
            file='',  # 後で更新
            status=STATUS_PROCESSING
        )

        # 予約録画レコードを作成
        scheduled_recording = ScheduledRecording.objects.create(
            uploaded_file=uploaded_file,
            meeting_id=meeting_details['meeting_id'],
            meeting_topic=meeting_details.get('topic', ''),
            meeting_url=meeting_url,
            meeting_password=meeting_details.get('password', ''),
            host_email=meeting_details.get('host_email', ''),
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=meeting_details.get('estimated_end_time'),
            estimated_duration=meeting_details.get('duration', 60),
            meeting_details=meeting_details,
            **user_options if user_options else {}
        )

        # 録画タスクをスケジュール
        recording_window = scheduled_recording.recording_window
        start_delay = int((recording_window['start'] - timezone.now()).total_seconds())

        if start_delay > 0:
            # 未来の時刻なのでスケジュール
            task = schedule_recording_task.apply_async(
                args=[str(scheduled_recording.id)],
                countdown=start_delay
            )

            scheduled_recording.celery_task_id = task.id
            scheduled_recording.save()

            logger.info(f"Scheduled recording {scheduled_recording.id} created for {scheduled_start_time}")
        else:
            # 即座に開始
            task = schedule_recording_task.delay(str(scheduled_recording.id))
            scheduled_recording.celery_task_id = task.id
            scheduled_recording.save()

            logger.info(f"Immediate recording {scheduled_recording.id} started")

        return {
            'success': True,
            'scheduled_recording_id': str(scheduled_recording.id),
            'uploaded_file_id': str(uploaded_file.id),
            'meeting_details': meeting_details
        }

    except Exception as e:
        logger.error(f"Error creating scheduled recording: {e}")
        return {
            'success': False,
            'error': str(e)
        }