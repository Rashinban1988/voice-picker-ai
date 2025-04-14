from django.core.management.base import BaseCommand
from openai import OpenAI
import os
from dotenv import load_dotenv
import logging
from voice_picker.models import UploadedFile
from voice_picker.views import text_generation_save

# 環境変数をロードする
load_dotenv()
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '全データの要約・課題・取り組み案を再生成します'

    def handle(self, *args, **options):
        uploaded_files = UploadedFile.objects.all()
        for uploaded_file in uploaded_files:
            # UploadedFileに紐づくTranscriptionを全て取得
            uploaded_file = text_generation_save(uploaded_file)
            if not uploaded_file:
                continue
            print(f"要約結果: {uploaded_file.summarization}")
            print(f"課題: {uploaded_file.issue}")
            print(f"取り組み案: {uploaded_file.solution}")
