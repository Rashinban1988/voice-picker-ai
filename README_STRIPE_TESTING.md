# Stripeサブスクリプション機能のテスト方法

## 概要

このドキュメントでは、Stripeサブスクリプション機能のテスト方法について説明します。

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

### よくある問題

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

### ログの確認

```bash
# Djangoのログを確認
tail -f backend/logs/django.log

# APIのログを確認
tail -f backend/logs/api.log
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