# LP Analytics System 設計ドキュメント

## 📋 概要

ランディングページ（LP）のユーザー行動を分析するための自社開発システム。Xserver VPS環境で動作し、CDN代替として静的ファイル配信機能を含む。

## 🏗️ システム構成

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   顧客のLP     │    │   Xserver VPS    │    │  管理画面       │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │lp-analytics.js│ ────→ │ Django REST   │ ────→ │ 分析ダッシュ  │ │
│ └─────────────┘ │    │ │     API       │ │    │ │ ボード       │ │
│                 │    │ └──────────────┘ │    │ └─────────────┘ │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │                 │
│ │data-track="*"│ │    │ │ PostgreSQL   │ │    │                 │
│ └─────────────┘ │    │ │    /MySQL     │ │    │                 │
└─────────────────┘    │ └──────────────┘ │    └─────────────────┘
                       └──────────────────┘
```

## 🗄️ データベース設計

### テーブル構成

#### 1. TrackingProject（トラッキングプロジェクト）
```sql
- id: UUID (PK)
- name: プロジェクト名
- tracking_id: トラッキングID（自動生成）
- domain: 対象ドメイン
- organization_id: 組織ID (FK)
- is_active: 有効フラグ
- created_at: 作成日時
- updated_at: 更新日時
```

#### 2. PageView（ページビュー）
```sql
- id: UUID (PK)
- project_id: プロジェクトID (FK)
- session_id: セッションID
- page_url: ページURL
- page_title: ページタイトル
- referrer: 参照元URL
- user_agent: ユーザーエージェント
- ip_address: IPアドレス
- screen_width: 画面幅
- screen_height: 画面高
- created_at: 作成日時
```

#### 3. UserInteraction（ユーザーインタラクション）
```sql
- id: UUID (PK)
- page_view_id: ページビューID (FK)
- event_type: イベントタイプ（click, scroll, mousemove等）
- x_coordinate: X座標
- y_coordinate: Y座標
- scroll_percentage: スクロール率
- element_selector: 要素セレクタ
- element_text: 要素テキスト
- viewport_width: ビューポート幅
- viewport_height: ビューポート高
- timestamp: イベント発生時刻
- created_at: 作成日時
```

#### 4. HeatmapData（ヒートマップ集計データ）
```sql
- id: UUID (PK)
- project_id: プロジェクトID (FK)
- page_url: ページURL
- x_coordinate: X座標
- y_coordinate: Y座標
- click_count: クリック数
- hover_count: ホバー数
- date: 集計日
- updated_at: 更新日時
```

#### 5. ScrollDepth（スクロール深度集計）
```sql
- id: UUID (PK)
- project_id: プロジェクトID (FK)
- page_url: ページURL
- depth_percentage: スクロール深度
- user_count: ユーザー数
- date: 集計日
- updated_at: 更新日時
```

## 🔧 API設計

### データ収集API（認証不要）

#### POST `/analytics/api/page-view/`
ページビューを記録
```json
{
  "tracking_id": "lp_ABC123XYZ789",
  "session_id": "sess_1234567890_abc123",
  "page_url": "https://example.com/lp",
  "page_title": "テストLP",
  "referrer": "https://google.com",
  "user_agent": "Mozilla/5.0...",
  "screen_width": 1920,
  "screen_height": 1080
}
```

#### POST `/analytics/api/interactions/`
ユーザーインタラクションを記録（バッチ送信対応）
```json
{
  "events": [
    {
      "page_view_id": "uuid-here",
      "event_type": "click",
      "x_coordinate": 100,
      "y_coordinate": 200,
      "element_selector": "button#cta-button.btn-primary",
      "element_text": "今すぐ申し込む",
      "viewport_width": 1200,
      "viewport_height": 800,
      "timestamp": "2025-08-17T14:30:00Z"
    }
  ]
}
```

### 分析API（認証必要）

#### GET `/analytics/api/dashboard/{project_id}/heatmap_data/`
ヒートマップデータの取得
```json
{
  "success": true,
  "data": [
    {"x": 100, "y": 200, "value": 1},
    {"x": 150, "y": 250, "value": 3}
  ],
  "total_clicks": 125
}
```

#### GET `/analytics/api/dashboard/{project_id}/scroll_data/`
スクロールデータの取得
```json
{
  "success": true,
  "data": {
    "25": 100,   // 25%地点まで100人
    "50": 75,    // 50%地点まで75人
    "75": 50,    // 75%地点まで50人
    "100": 25    // 100%地点まで25人
  },
  "total_users": 100
}
```

## 📊 JavaScript SDK仕様

### 初期化
```javascript
const analytics = new LPAnalytics({
    trackingId: 'lp_ABC123XYZ789',
    apiEndpoint: 'https://your-domain.com'
});
```

### 自動収集イベント
- **ページビュー**: ページ読み込み時
- **クリック**: 全要素のクリック座標
- **スクロール**: スクロール深度（最大値のみ）
- **マウス移動**: 軌跡データ（間引き処理）
- **リサイズ**: ウィンドウサイズ変更
- **フォーカス**: フォーム要素のフォーカス

### カスタムイベント
```javascript
analytics.trackCustomEvent('button_click', {
    button_type: 'cta',
    section: 'hero'
});
```

### パフォーマンス最適化
- **スロットリング**: マウス移動・スクロールは100ms間隔
- **バッチ送信**: 10イベントまたは5秒間隔
- **セッション管理**: ブラウザ セッション単位

## 🔒 セキュリティ・プライバシー

### データ収集方針
- **個人識別情報**: 収集しない
- **IPアドレス**: 統計目的のみ、匿名化推奨
- **クッキー**: セッションIDのみ、一時的
- **GDPR対応**: 必要に応じてオプトアウト機能

### セキュリティ対策
- **CORS設定**: 許可ドメインのみ
- **レート制限**: IP別リクエスト制限
- **データ検証**: 不正データの除外
- **ログ管理**: アクセスログの監視

## 🚀 デプロイ手順（Xserver VPS）

### 1. 環境準備
```bash
# マイグレーション
docker compose exec django python manage.py makemigrations analytics
docker compose exec django python manage.py migrate analytics

# 静的ファイル収集
docker compose exec django python manage.py collectstatic
```

### 2. nginx設定
```nginx
# /etc/nginx/sites-available/your-site
location /static/ {
    alias /path/to/your/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location /analytics/api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### 3. 管理画面での設定
1. Django管理画面でTrackingProjectを作成
2. 自動生成されたtracking_idを取得
3. 顧客LPにJavaScript SDKを実装

## 📈 使用例

### HTML実装例
```html
<!DOCTYPE html>
<html>
<head>
    <title>テストLP</title>
</head>
<body>
    <!-- トラッキング対象の要素 -->
    <button id="cta-button" data-track="main-cta">
        今すぐ申し込む
    </button>
    
    <div id="features" data-track="features-section">
        <h2>特徴</h2>
        <!-- コンテンツ -->
    </div>

    <!-- LP Analytics SDK -->
    <script src="https://your-domain.com/static/js/lp-analytics.js"></script>
    <script>
        const analytics = new LPAnalytics({
            trackingId: 'lp_YOUR_TRACKING_ID',
            apiEndpoint: 'https://your-domain.com'
        });
        
        // カスタムイベント
        analytics.trackCustomEvent('video_played', {
            video_id: 'intro_video',
            duration: 30
        });
    </script>
</body>
</html>
```

### 管理画面での分析
1. **プロジェクト一覧**: `/admin/analytics/trackingproject/`
2. **ページビュー**: `/admin/analytics/pageview/`
3. **インタラクション**: `/admin/analytics/userinteraction/`
4. **API経由**: REST APIで詳細分析

## 🔄 今後の拡張予定

### Phase 2
- リアルタイムダッシュボード
- ヒートマップ可視化UI
- A/Bテスト機能

### Phase 3
- 機械学習による行動予測
- セッション録画機能
- 高度なセグメント分析

## ⚡ パフォーマンス考慮

### データベース最適化
- インデックス設定済み
- パーティショニング（日付別）
- 古いデータの自動削除

### サーバー負荷軽減
- 非同期処理（Celery）
- キャッシュ活用（Redis）
- CDN活用（静的ファイル）

## 🧪 テスト

### テストページ
`analytics/test_sdk.html` でSDKの動作テストが可能

### APIテスト
```bash
# ページビューテスト
curl -X POST http://localhost:8000/analytics/api/page-view/ \
  -H "Content-Type: application/json" \
  -d '{"tracking_id":"lp_TEST123456789","session_id":"test_session",...}'

# インタラクションテスト
curl -X POST http://localhost:8000/analytics/api/interactions/ \
  -H "Content-Type: application/json" \
  -d '{"events":[{"page_view_id":"uuid","event_type":"click",...}]}'
```

## 📞 問い合わせ・サポート

システムに関する問い合わせは開発チームまで。

---

*Last updated: 2025-08-17*
*Version: 1.0.0*