from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from voice_picker.models.meeting import Meeting, MeetingStatus
import logging
import threading
import time
from datetime import datetime, timedelta
import subprocess
import os

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
                meeting.recorded_file_path = recorded_file
                meeting.status = MeetingStatus.COMPLETED
                meeting.save()
                processing_logger.info(f'ミーティング録画完了: {meeting_id}')
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
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--use-fake-ui-for-media-stream')
            chrome_options.add_argument('--use-fake-device-for-media-stream')
            
            driver = webdriver.Chrome(options=chrome_options)
            
            driver.get(meeting.meeting_url)
            
            if meeting.meeting_platform == 'zoom':
                self.handle_zoom_meeting(driver, meeting)
            elif meeting.meeting_platform == 'teams':
                self.handle_teams_meeting(driver, meeting)
            elif meeting.meeting_platform == 'meet':
                self.handle_meet_meeting(driver, meeting)
            
            time.sleep(meeting.duration_minutes * 60)
            
            driver.quit()
            
            return f"/recordings/{meeting.id}.mp4"
            
        except Exception as e:
            processing_logger.error(f'ブラウザ録画エラー: {e}')
            return None

    def handle_zoom_meeting(self, driver, meeting):
        pass

    def handle_teams_meeting(self, driver, meeting):
        pass

    def handle_meet_meeting(self, driver, meeting):
        pass
