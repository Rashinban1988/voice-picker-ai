import os
from celery import Celery

# DjangoのsettingsモジュールをCeleryに設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Celeryの設定をDjango settingsからロード
# namespace='CELERY'とすることで、settings.pyのCELERY_で始まる変数が自動的に読み込まれます
app.config_from_object('django.conf:settings', namespace='CELERY')

# Djangoアプリ内のすべてのタスクを自動的に検出
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')