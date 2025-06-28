from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from voice_picker.models.meeting import Meeting, MeetingStatus
from voice_picker.models.uploaded_file import UploadedFile
import logging
import threading
import time
from datetime import datetime, timedelta
import subprocess
import os
import shutil

processing_logger = logging.getLogger('processing')

class Command(BaseCommand):
    help = 'ミーティングを自動録画する'

    def handle(self, *args, **options):
        now = timezone.now()
        upcoming_meetings = Meeting.objects.filter(
            status=MeetingStatus.SCHEDULED,
            scheduled_time__lte=now + timedelta(minutes=5),
            scheduled_time__gte=now - timedelta(minutes=5),
            exist=True
        )

        if not upcoming_meetings.exists():
            processing_logger.info('録画対象のミーティングがありませんでした。')
            return

        meeting_ids = list(upcoming_meetings.values_list('id', flat=True))
        Meeting.objects.filter(id__in=meeting_ids).update(status=MeetingStatus.RECORDING)
        processing_logger.info(f'{len(meeting_ids)}件のミーティングを録画開始に設定しました。')

        threads = []
        for meeting_id in meeting_ids:
            thread = threading.Thread(target=self.record_meeting, args=(meeting_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        processing_logger.info('全ミーティングの録画処理が完了しました。')

    def record_meeting(self, meeting_id):
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            processing_logger.info(f'ミーティング録画開始: {meeting.meeting_url}')

            recorded_file = self.start_browser_recording(meeting)
            
            if recorded_file:
                uploaded_file = self.create_uploaded_file_from_recording(meeting, recorded_file)
                
                meeting.recorded_file_path = recorded_file
                meeting.uploaded_file = uploaded_file
                meeting.status = MeetingStatus.COMPLETED
                meeting.save()
                processing_logger.info(f'ミーティング録画完了: {meeting_id}, UploadedFile ID: {uploaded_file.id}')
            else:
                meeting.status = MeetingStatus.ERROR
                meeting.save()
                processing_logger.error(f'ミーティング録画失敗: {meeting_id}')

        except Exception as e:
            Meeting.objects.filter(id=meeting_id).update(status=MeetingStatus.ERROR)
            processing_logger.exception(f"ミーティング録画でエラーが発生しました。Meeting ID: {meeting_id}")

    def start_browser_recording(self, meeting):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.common.exceptions import WebDriverException
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--use-fake-ui-for-media-stream')
            chrome_options.add_argument('--use-fake-device-for-media-stream')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            driver.get(meeting.meeting_url)
            time.sleep(10)
            
            if meeting.meeting_platform == 'zoom':
                self.handle_zoom_meeting(driver, meeting)
            elif meeting.meeting_platform == 'teams':
                self.handle_teams_meeting(driver, meeting)
            elif meeting.meeting_platform == 'meet':
                self.handle_meet_meeting(driver, meeting)
            
            recording_file = f"/tmp/meeting_{meeting.id}.mp4"
            
            self.monitor_meeting_until_end(driver, meeting, recording_file)
            
            driver.quit()
            return recording_file
            
        except Exception as e:
            processing_logger.error(f'ブラウザ録画エラー: {e}')
            return None

    def monitor_meeting_until_end(self, driver, meeting, recording_file):
        """ミーティングが終了するまで監視"""
        meeting_active = True
        max_duration = meeting.duration_minutes * 60
        start_time = time.time()
        
        while meeting_active:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            if elapsed_time > max_duration:
                processing_logger.info(f'最大録画時間に達しました: {meeting.id}')
                break
            
            if self.is_meeting_ended(driver, meeting.meeting_platform):
                processing_logger.info(f'ミーティングが終了しました: {meeting.id}')
                break
            
            try:
                driver.current_url
            except:
                processing_logger.info(f'ブラウザプロセスが終了しました: {meeting.id}')
                break
            
            time.sleep(30)

    def is_meeting_ended(self, driver, platform):
        """ミーティング終了を検出"""
        try:
            page_source = driver.page_source.lower()
            if platform == 'zoom':
                return "meeting has ended" in page_source or "the meeting has been ended" in page_source
            elif platform == 'teams':
                return "meeting has ended" in page_source or "call ended" in page_source
            elif platform == 'meet':
                return "meeting ended" in page_source or "you left the meeting" in page_source
            return False
        except Exception:
            return False

    def handle_zoom_meeting(self, driver, meeting):
        pass

    def handle_teams_meeting(self, driver, meeting):
        pass

    def handle_meet_meeting(self, driver, meeting):
        pass

    def create_uploaded_file_from_recording(self, meeting, recorded_file_path):
        """録画ファイルからUploadedFileレコードを作成（会議情報を保持）"""
        try:
            from django.core.files import File
            
            meeting_date = meeting.scheduled_time.strftime('%Y年%m月%d日_%H時%M分')
            platform_name = dict(meeting._meta.get_field('meeting_platform').choices)[meeting.meeting_platform]
            filename = f"{platform_name}会議_{meeting_date}.mp4"
            
            uploaded_file = UploadedFile(organization=meeting.organization)
            
            if os.path.exists(recorded_file_path):
                with open(recorded_file_path, 'rb') as f:
                    django_file = File(f, name=filename)
                    uploaded_file.file.save(filename, django_file, save=False)
                
                uploaded_file.save()
                
                try:
                    os.remove(recorded_file_path)
                    processing_logger.info(f'元の録画ファイルを削除: {recorded_file_path}')
                except OSError:
                    processing_logger.warning(f'元の録画ファイルの削除に失敗: {recorded_file_path}')
            else:
                processing_logger.error(f'録画ファイルが見つかりません: {recorded_file_path}')
                raise FileNotFoundError(f'録画ファイルが見つかりません: {recorded_file_path}')
            
            processing_logger.info(f'UploadedFileレコード作成完了: {uploaded_file.id}')
            processing_logger.info(f'ファイルパス: {uploaded_file.file.path}')
            processing_logger.info(f'会議情報: {platform_name} - {meeting_date}')
            return uploaded_file
            
        except Exception as e:
            processing_logger.error(f'UploadedFileレコード作成エラー: {e}')
            raise
