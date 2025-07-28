# A/Bテスト機能実装ガイド

## 概要

Voice Picker AIのランディングページ用A/Bテスト機能の完全実装です。
フロントエンド（Next.js）とバックエンド（Django）が連携して、効果測定を行います。

## 📁 実装ファイル一覧

### フロントエンド（Next.js）
```
vp-frontend/
├── src/utils/abTestTracker.ts          # A/Bテストトラッキングユーティリティ
├── src/app/lp/page.tsx                 # LP（A/Bパターン実装済み）
└── src/app/auth/register-success/page.tsx  # コンバージョン追跡
```

### バックエンド（Django）
```
vp-backend/
└── ab_test/
    ├── __init__.py
    ├── apps.py                         # アプリ設定
    ├── models.py                       # データベースモデル
    ├── serializers.py                  # APIシリアライザー
    ├── views.py                        # APIビュー
    ├── urls.py                         # URLパターン
    ├── api_urls.py                     # API URL設定
    ├── admin.py                        # Django Admin設定
    ├── migrations/
    │   ├── __init__.py
    │   └── 0001_initial.py             # 初期マイグレーション
    └── management/commands/
        └── generate_ab_test_summary.py # 日次サマリー生成コマンド
```

## 🚀 セットアップ手順

### 1. バックエンドセットアップ

#### Docker環境での実行
```bash
# コンテナを起動
cd vp-backend
docker-compose up -d

# マイグレーション実行（既存のモデルエラーがある場合は手動で解決）
docker-compose exec django python manage.py migrate ab_test

# スーパーユーザー作成（管理画面アクセス用）
docker-compose exec django python manage.py createsuperuser
```

#### 設定確認
`config/settings.py`の`INSTALLED_APPS`に以下が追加されていることを確認：
```python
INSTALLED_APPS = [
    # ...
    'ab_test.apps.AbTestConfig',  # A/Bテスト
]
```

### 2. フロントエンドセットアップ

#### 環境変数確認
`.env.local`にバックエンドAPIのURLが設定されていることを確認：
```
NEXT_PUBLIC_DJANGO_API_BASE_URL=http://localhost:8000
```

#### ビルド確認
```bash
cd vp-frontend
npm run build
```

## 📊 API エンドポイント

### 1. イベントトラッキング
```http
POST /api/ab-test/track/
Content-Type: application/json

{
    "variant": "A",
    "event": "page_view",
    "timestamp": 1707123456789,
    "sessionId": "session_1707123456_abc123",
    "userId": "user123"  // オプション（コンバージョン時のみ）
}
```

**レスポンス例:**
```json
{
    "status": "success",
    "message": "Event tracked successfully",
    "event_id": 123
}
```

### 2. 統計情報取得
```http
GET /api/ab-test/stats/
GET /api/ab-test/stats/?days=30
GET /api/ab-test/stats/?start_date=2024-01-01&end_date=2024-01-31
```

**レスポンス例:**
```json
{
    "summary": {
        "variantA": {
            "pageViews": 1000,
            "registerClicks": 150,
            "loginClicks": 25,
            "conversions": 45,
            "uniqueSessions": 980,
            "conversionRate": 0.0459,
            "clickThroughRate": 0.15
        },
        "variantB": {
            "pageViews": 980,
            "registerClicks": 180,
            "loginClicks": 30,
            "conversions": 60,
            "uniqueSessions": 960,
            "conversionRate": 0.0625,
            "clickThroughRate": 0.1837
        }
    },
    "period": {
        "startDate": "2024-01-01",
        "endDate": "2024-01-31"
    },
    "totalDays": 31
}
```

### 3. 日別統計
```http
GET /api/ab-test/stats/daily/
```

### 4. イベント一覧（管理用）
```http
GET /api/ab-test/events/
GET /api/ab-test/events/?variant=A&event=conversion&limit=50
```

## 🎯 使用方法

### 1. A/Bテストの実行

#### 自動バリアント割り当て
```bash
# 通常アクセス（50%の確率でA/B決定）
https://yourdomain.com/lp
```

#### 強制バリアント指定（テスト用）
```bash
# Aパターンを強制表示
https://yourdomain.com/lp?variant=A

# Bパターンを強制表示  
https://yourdomain.com/lp?variant=B
```

### 2. 統計確認

#### 管理画面での確認
```bash
# Django Admin画面
https://yourdomain.com/admin/ab_test/
```

#### API経由での確認
```bash
# 基本統計
curl -X GET "http://localhost:8000/api/ab-test/stats/"

# 期間指定統計
curl -X GET "http://localhost:8000/api/ab-test/stats/?days=7"

# 日別統計
curl -X GET "http://localhost:8000/api/ab-test/stats/daily/"
```

### 3. 日次サマリー生成（任意）

パフォーマンス向上のため、日次でサマリーデータを生成できます：

```bash
# 昨日のサマリーを生成
docker-compose exec django python manage.py generate_ab_test_summary

# 特定日のサマリーを生成
docker-compose exec django python manage.py generate_ab_test_summary --date 2024-01-15

# 過去7日分のサマリーを生成
docker-compose exec django python manage.py generate_ab_test_summary --days 7
```

#### Crontab設定例
```bash
# 毎日午前1時に前日のサマリーを生成
0 1 * * * cd /path/to/vp-backend && docker-compose exec django python manage.py generate_ab_test_summary
```

## 📈 追跡されるイベント

### イベントタイプ
1. **page_view**: LPページ表示
2. **register_click**: 登録ボタンクリック
3. **login_click**: ログインボタンクリック  
4. **conversion**: 実際の登録完了

### データ収集項目
- バリアント（A/B）
- イベントタイプ
- セッションID
- タイムスタンプ
- IPアドレス（統計用）
- User-Agent（統計用）
- ユーザーID（コンバージョン時）

## 🎨 A/Bパターンの詳細

### Aパターン（明るいデザイン）
- 明るいグラデーション背景
- 会議動画のメインビジュアル
- 「今すぐ無料で始める」CTA

### Bパターン（ダークデザイン）
- ダークグラデーション背景  
- 重なり合うUIプレビュー
- 「無料トライアルを開始」CTA

## 🔧 カスタマイズ

### 新しいイベント追加
1. `models.py`の`EVENT_CHOICES`に追加
2. `serializers.py`のバリデーションを更新
3. フロントエンドのトラッキングコードに追加
4. マイグレーション実行

### 新しいバリアント追加
1. `models.py`の`VARIANT_CHOICES`に追加
2. フロントエンドのバリアント判定ロジックを更新
3. LP用コンポーネントを追加

## 🚨 本番環境での注意事項

### セキュリティ
1. API権限設定の見直し
   ```python
   # views.py
   permission_classes = [IsAuthenticated]  # 適切な権限設定
   ```

2. レート制限の設定
   ```python
   # Django REST framework throttling
   REST_FRAMEWORK = {
       'DEFAULT_THROTTLE_CLASSES': [
           'rest_framework.throttling.AnonRateThrottle',
       ],
       'DEFAULT_THROTTLE_RATES': {
           'anon': '100/hour'
       }
   }
   ```

### パフォーマンス
1. データベースインデックスの最適化
2. 古いイベントデータのアーカイブ
3. CDN経由でのAPI配信

### プライバシー
1. IPアドレスの匿名化処理
2. GDPRコンプライアンス対応
3. データ保持期間の設定

## 📊 分析のポイント

### 統計指標
- **コンバージョン率**: conversions / uniqueSessions
- **クリック率**: registerClicks / pageViews  
- **統計的有意性**: 十分なサンプルサイズでの検証

### 分析項目
1. バリアント別のコンバージョン率比較
2. 時系列でのトレンド分析
3. デバイス・ブラウザ別の効果測定
4. 流入元別の効果分析

## 🐛 トラブルシューティング

### よくある問題

1. **マイグレーションエラー**
   ```bash
   # 手動でマイグレーション適用
   docker-compose exec django python manage.py migrate ab_test --fake-initial
   ```

2. **APIエラー**
   ```bash
   # ログ確認
   docker-compose logs django
   ```

3. **フロントエンドのSSRエラー**
   - `abTestTracker.ts`でブラウザ環境チェック実装済み

### デバッグ方法
```javascript
// ブラウザコンソールで確認
console.log(sessionStorage.getItem('lp-variant'))
console.log(localStorage.getItem('ab-test-events'))
```

## 📝 ログ出力

### Django側
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f'A/B test event tracked: {event}')
```

### フロントエンド側
```javascript
// 開発環境でのみログ出力
if (process.env.NODE_ENV === 'development') {
    console.log('A/B test event:', eventData)
}
```

---

以上でA/Bテスト機能の実装は完了です。質問がある場合は、開発チームまでお問い合わせください。