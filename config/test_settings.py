from .settings import *

# テスト用データベース設定
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# テスト用のStripe設定
STRIPE_PUBLISHABLE_KEY = 'pk_test_test'
STRIPE_SECRET_KEY = 'sk_test_test'
STRIPE_WEBHOOK_SECRET = 'whsec_test'

# テスト用のログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'api': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
} 