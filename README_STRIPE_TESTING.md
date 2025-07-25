# Stripeサブスクリプション機能のテスト方法

## 概要

このドキュメントでは、Stripeサブスクリプション機能のテスト方法について説明します。

**現在の状況**: 10件のテストがすべて成功し、Stripe APIをモック化することで安定したテスト環境が構築されています。

## 本番運用前チェックリスト

### 🔒 セキュリティ設定

- [x] HTTPS強制リダイレクト設定
- [x] セキュリティヘッダー設定
- [x] CORS設定
- [x] Webhook署名検証
- [ ] **本番環境での追加セキュリティ設定**

```python
# settings.py 本番環境用追加設定
if not DEBUG:
    # HTTPS設定
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1年
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # セッション設定
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # その他のセキュリティ設定
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
```

### 🌐 本番環境設定

- [ ] **Stripe本番環境キーの設定**
- [ ] **本番Webhookエンドポイントの設定**
- [ ] **ドメイン設定の確認**

```bash
# 本番環境変数設定例
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
DEBUG=False
ALLOWED_HOSTS=voice-picker-ai.com,django.voice-picker-ai.com
```

### 📊 監視・ログ設定

- [x] 日次ログローテーション
- [x] 30日間バックアップ保持
- [ ] **本番環境でのログ監視設定**

```python
# 本番環境用ログ設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'django_file': {
            'level': 'WARNING',  # 本番ではWARNING以上
            'class': 'config.logging_handlers.DailyRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'django'),
            'formatter': 'verbose',
            'when': 'midnight',
            'backupCount': 30,
        },
        'stripe_file': {
            'level': 'INFO',
            'class': 'config.logging_handlers.DailyRotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'stripe'),
            'formatter': 'verbose',
            'when': 'midnight',
            'backupCount': 90,  # Stripeログは90日間保持
        },
    },
    'loggers': {
        'django': {
            'handlers': ['django_file'],
            'level': 'WARNING',
            'propagate': True,
        },
        'member_management.views': {
            'handlers': ['stripe_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### 🔄 バックアップ・復旧

- [ ] **データベースバックアップ設定**
- [ ] **Stripeデータ同期確認**
- [ ] **障害復旧手順書作成**

```bash
# データベースバックアップ例
#!/bin/bash
# backup_db.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/database"
DB_NAME="your_db_name"

# バックアップ作成
mysqldump -u $DB_USER -p$DB_PASSWORD $DB_NAME > $BACKUP_DIR/backup_$DATE.sql

# 7日以上古いバックアップを削除
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

### 📈 パフォーマンス最適化

- [ ] **データベースインデックス最適化**
- [ ] **キャッシュ設定**
- [ ] **CDN設定**

```python
# キャッシュ設定例
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

## テストの種類

### 1. ユニットテスト

#### 実行方法

```bash
# 特定のテストファイルを実行
python manage.py test member_management.tests.test_stripe

# 特定のテストクラスを実行
python manage.py test member_management.tests.test_stripe.StripeCheckoutSessionTest

# 特定のテストメソッドを実行
python manage.py test member_management.tests.test_stripe.StripeCheckoutSessionTest.test_create_checkout_session_success
```

#### テスト内容

- **StripeCheckoutSessionTest**: チェックアウトセッション作成のテスト
- **StripePortalTest**: 顧客ポータル機能のテスト
- **StripeWebhookTest**: Webhook処理のテスト
- **StripeModelTest**: モデルの動作テスト
- **StripeErrorHandlingTest**: エラーハンドリングのテスト

#### テストの特徴

- **モック化**: Stripe API呼び出しをモック化し、外部依存を排除
- **高速実行**: 外部APIに依存しないため、テストが高速に実行される
- **安定性**: ネットワーク問題やAPI制限の影響を受けない

### 2. 統合テスト

#### Stripe CLIを使用したテスト

```bash
# Stripe CLIのインストール（初回のみ）
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.dev/stripe-cli-debian-local stable main" | sudo tee -a /etc/apt/sources.list.d/stripe.list
sudo apt update
sudo apt install stripe

# Stripe CLIでログイン
stripe login

# Webhookの転送を開始
stripe listen --forward-to localhost:8000/api/webhook/stripe/

# テスト用のチェックアウトセッションを作成
stripe checkout sessions create \
  --success-url="http://localhost:3000/success" \
  --cancel-url="http://localhost:3000/cancel" \
  --line-items="price_data[0][price]=price_test_123,price_data[0][quantity]=1" \
  --mode=subscription
```

### 3. 手動テスト

#### テスト用の環境変数設定

```bash
# .envファイルに以下を追加
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

#### テスト手順

1. **チェックアウトセッション作成のテスト**
   ```bash
   curl -X POST http://localhost:8000/api/subscriptions/create_checkout_session/ \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"plan_id": "PLAN_UUID"}'
   ```

2. **顧客ポータルのテスト**
   ```bash
   curl -X POST http://localhost:8000/api/subscriptions/manage_portal/ \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json"
   ```

3. **Webhookのテスト**
   ```bash
   # Stripe CLIを使用してテストイベントを送信
   stripe trigger checkout.session.completed
   stripe trigger customer.subscription.updated
   stripe trigger customer.subscription.deleted
   ```

## テストデータの準備

### テスト用プランの作成

```python
# Django shellで実行
from member_management.models import SubscriptionPlan

# テスト用プランを作成
plan = SubscriptionPlan.objects.create(
    name="テストプラン",
    description="テスト用プラン",
    price=1000,
    max_duration=100,
    stripe_price_id="price_test_123",
    is_active=True
)
```

### テスト用ユーザーの作成

```python
from member_management.models import Organization, User

# テスト用組織を作成
org = Organization.objects.create(
    name="テスト組織",
    email="test@example.com"
)

# テスト用ユーザーを作成
user = User.objects.create_user(
    username="testuser",
    email="test@example.com",
    password="testpass123",
    organization=org
)
```

## ログ設定

### Webhook処理の詳細ログ

```python
# settings.pyでログレベルを設定
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'backend/logs/django.log',
        },
    },
    'loggers': {
        'member_management.views': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

## テストカバレッジ

### カバレッジの確認

```bash
# coverageをインストール
pip install coverage

# テストを実行してカバレッジを測定
coverage run --source='.' manage.py test member_management.tests.test_stripe

# カバレッジレポートを表示
coverage report

# HTMLレポートを生成
coverage html
```

## トラブルシューティング

### よくある問題と解決方法

1. **Stripe APIキーが設定されていない**
   ```bash
   # .envファイルにStripe APIキーを設定
   STRIPE_SECRET_KEY=sk_test_...
   ```

2. **Webhookシークレットが設定されていない**
   ```bash
   # .envファイルにWebhookシークレットを設定
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

3. **テストデータが存在しない**
   ```bash
   # テストデータを作成
   python manage.py shell
   # 上記のテストデータ作成コードを実行
   ```

4. **MySQLのテストデータベース作成権限エラー**
   ```bash
   # MySQLでテスト用データベースを作成
   mysql -u root -p
   CREATE DATABASE test_vp_db;
   GRANT ALL PRIVILEGES ON test_vp_db.* TO 'your_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

5. **カスタムユーザーマネージャーのcreate_userメソッドエラー**
   ```python
   # member_management/models.pyでcreate_userメソッドを実装
   def create_user(self, username, email, password=None, **extra_fields):
       if not username:
           raise ValueError('ユーザー名は必須です')
       email = self.normalize_email(email)
       user = self.model(username=username, email=email, **extra_fields)
       user.set_password(password)
       user.save(using=self._db)
       return user
   ```

6. **URL名の不一致エラー（NoReverseMatch）**
   ```python
   # urls.pyでURL名を正しく設定
   path('create_checkout_session/', views.create_checkout_session, name='create_checkout_session'),
   path('manage_portal/', views.manage_portal, name='manage_portal'),
   ```

7. **UUID形式エラー**
   ```python
   # テストでUUIDを正しい形式で生成
   import uuid
   plan_id = str(uuid.uuid4())
   ```

### ログの確認

```bash
# Djangoのログを確認
tail -f backend/logs/django.log

# APIのログを確認
tail -f backend/logs/api.log

# Webhook処理の詳細ログを確認
grep "Webhook" backend/logs/django.log
```

## 本番環境でのテスト

### 本番環境での注意点

1. **テストモードの使用**
   - 本番環境でもStripeのテストモードを使用
   - 実際の課金は発生しない

2. **Webhookの設定**
   - StripeダッシュボードでWebhookエンドポイントを設定
   - 本番環境のURLを指定

3. **ログの監視**
   - 本番環境ではログを定期的に確認
   - エラーが発生した場合は即座に対応

## セキュリティテスト

### セキュリティチェック項目

1. **Webhook署名の検証**
   - 不正な署名でのリクエストを拒否
   - 署名なしのリクエストを拒否

2. **アクセス制御**
   - 未認証ユーザーのアクセスを拒否
   - 無効なサブスクリプションでのアクセスを制限

3. **入力値検証**
   - 不正なプランIDを拒否
   - 不正なデータ形式を拒否

## パフォーマンステスト

### 負荷テスト

```bash
# Apache Benchを使用した負荷テスト
ab -n 100 -c 10 -H "Authorization: Bearer YOUR_JWT_TOKEN" \
   http://localhost:8000/api/subscriptions/
```

### レスポンス時間の測定

```bash
# curlでレスポンス時間を測定
curl -w "@curl-format.txt" -o /dev/null -s \
     http://localhost:8000/api/subscriptions/
```

## 継続的インテグレーション

### GitHub Actionsでの自動テスト

```yaml
# .github/workflows/test.yml
name: Stripe Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python manage.py test member_management.tests.test_stripe
        env:
          STRIPE_SECRET_KEY: ${{ secrets.STRIPE_SECRET_KEY }}
          STRIPE_WEBHOOK_SECRET: ${{ secrets.STRIPE_WEBHOOK_SECRET }}
```

## テスト実行スクリプト

### 自動テスト実行

```bash
#!/bin/bash
# run_stripe_tests.sh

echo "Stripeサブスクリプション機能のテストを開始します..."

# 環境変数の確認
if [ -z "$STRIPE_SECRET_KEY" ]; then
    echo "警告: STRIPE_SECRET_KEYが設定されていません"
fi

if [ -z "$STRIPE_WEBHOOK_SECRET" ]; then
    echo "警告: STRIPE_WEBHOOK_SECRETが設定されていません"
fi

# テストの実行
echo "ユニットテストを実行中..."
python manage.py test member_management.tests.test_stripe --verbosity=2

# テスト結果の確認
if [ $? -eq 0 ]; then
    echo "✅ すべてのテストが成功しました！"
else
    echo "❌ テストが失敗しました"
    exit 1
fi

echo "テスト完了"
```

## 現在の実装状況

### 完了済み機能

- ✅ Stripeチェックアウトセッション作成
- ✅ 顧客ポータル機能
- ✅ Webhook処理（checkout.session.completed, customer.subscription.updated, customer.subscription.deleted）
- ✅ サブスクリプション状態管理
- ✅ エラーハンドリング
- ✅ セキュリティミドルウェア
- ✅ 包括的なユニットテスト（10件すべて成功）
- ✅ モック化による安定したテスト環境

### 今後の改善点

- 🔄 UUID形式エラーのハンドリング改善
- 🔄 より詳細なWebhook処理ログ
- 🔄 パフォーマンス最適化

## 本番運用準備状況

### ✅ 準備完了

- **セキュリティ**: HTTPS、セキュリティヘッダー、CORS設定済み
- **Stripe機能**: 基本機能、Webhook処理、エラーハンドリング実装済み
- **ログ**: 日次ローテーション、バックアップ保持設定済み
- **テスト**: 10件のテストが成功、モック化による安定性確保

### ⚠️ 本番運用前に必要な作業

1. **本番環境設定**
   - Stripe本番環境キーの設定
   - 本番Webhookエンドポイントの設定
   - ドメイン設定の確認

2. **セキュリティ強化**
   - 本番環境用セキュリティ設定の追加
   - セッション設定の強化

3. **監視・バックアップ**
   - 本番環境でのログ監視設定
   - データベースバックアップ設定
   - 障害復旧手順書作成

4. **パフォーマンス最適化**
   - データベースインデックス最適化
   - キャッシュ設定
   - CDN設定

**結論**: 基本的な機能は実装済みですが、本番運用には上記の追加作業が必要です。 