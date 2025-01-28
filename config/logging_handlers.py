import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

class DailyRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, *args, **kwargs):
        self.base_filename = filename
        super().__init__(self.get_file_name(), *args, **kwargs)

    def get_file_name(self):
        # 現在の日付を取得し、ファイル名を生成
        date_str = datetime.now().strftime("%Y-%m-%d")
        return f"{self.base_filename}{date_str}.log"

    def doRollover(self):
        # ローテーション処理をカスタマイズ
        self.close()
        self.baseFilename = self.get_file_name()
        self.mode = 'a'
        self.stream = self._open()