# Stripe統合テスト用設定
# 本番環境には影響しません

import os
from pathlib import Path
from datetime import timedelta
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 基本設定
SECRET_KEY = config('DJANGO_SECRET_KEY', default='test-secret-key-for-stripe-integration-testing')

# デバッグモード（テスト環境用）
DEBUG = True

# ホスト設定
ALLOWED_HOSTS = ['*']

# アプリケーション（最小構成）
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'member_management.apps.MemberManagementConfig',
    'tests',
]

# ユーザーモデル
AUTH_USER_MODEL = 'member_management.User'

# JWT設定
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

# REST Framework設定
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ミドルウェア（最小構成）
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# URL設定
ROOT_URLCONF = 'config.urls'

# テンプレート設定
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# テスト用データベース
import os
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db_test_integration.sqlite3'),
    }
}

# Next.js設定（テスト環境用デフォルト値を設定）
NEXT_JS_HOST = config('NEXT_JS_HOST', default='http://localhost')
NEXT_JS_PORT = config('NEXT_JS_PORT', default='3000')

# Stripe設定（テストモード）
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET')

# テストモードフラグ
STRIPE_TEST_MODE = True
TESTING_INTEGRATION = True

# テスト用アプリは既にINSTALLED_APPSに含まれています

# ロギング設定（詳細ログ）
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'stripe_integration_test.log',
        },
    },
    'loggers': {
        'stripe_integration': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

# CORS設定（ngrok用）
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    "https://*.ngrok.io",
    "https://*.ngrok-free.app",
]

# CSRFトークン設定（テスト環境用）
CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok.io",
    "https://*.ngrok-free.app",
]

# 国際化設定
LANGUAGE_CODE = 'ja'
TIME_ZONE = 'Asia/Tokyo'
USE_I18N = True
USE_TZ = True

# 静的ファイル設定
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_test')

# デフォルトフィールド設定
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# セキュリティ設定（テスト環境用に緩和）
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# キャッシュ無効化（テスト用）
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

print(f"🧪 Stripe統合テスト設定を読み込みました")
print(f"📊 データベース: {DATABASES['default']['NAME']}")
print(f"🔑 Stripeテストモード: {STRIPE_TEST_MODE}")
