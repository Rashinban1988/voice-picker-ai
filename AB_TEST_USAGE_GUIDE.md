# A/Bテストサマリー画面 使用ガイド

## 概要
A/Bテストサマリー画面では、LPページのA/Bテスト結果を日別・バリアント別に確認できます。

## アクセス方法
1. Django管理画面にアクセス: `http://localhost:8800/admin/`
2. 「🧪 A/Bテスト結果」リンクをクリック
3. または直接URL: `http://localhost:8800/admin/ab_test/abtestsummary/`

## サマリーデータの生成

### 自動生成（推奨）
Crontabで毎日実行するよう設定：
```bash
# 毎日午前2時に実行
0 2 * * * cd /path/to/project && python manage.py generate_ab_test_summary
```

### 手動生成
```bash
# 昨日のデータを生成
python manage.py generate_ab_test_summary

# 特定の日付を指定
python manage.py generate_ab_test_summary --date 2025-08-21

# 複数日分を一括生成
python manage.py generate_ab_test_summary --date 2025-08-15 --days 7
```

## 画面の見方

### 1. 統計情報セクション
- **総ページビュー数**: A/B両バリアントの合計
- **総登録クリック数**: 「無料トライアルを始める」ボタンのクリック数
- **総ログインクリック数**: 「ログイン」ボタンのクリック数
- **総コンバージョン数**: 実際に会員登録完了したユーザー数
- **平均コンバージョン率**: コンバージョン数 ÷ セッション数

### 2. バリアント別統計
- **Variant A**: 既存デザインの統計
- **Variant B**: 新デザインの統計
- **コンバージョン率の比較**: どちらのデザインが効果的かを判断

### 3. 直近7日間の統計
- 最近のパフォーマンストレンド
- 改善効果の確認

## データの流れ

### 1. イベント収集
LPページで以下のイベントが自動的に記録されます：
- `page_view`: ページ表示
- `register_click`: 登録ボタンクリック
- `login_click`: ログインボタンクリック
- `conversion`: 会員登録完了

### 2. セッション管理
- 各訪問者のセッションが`ABTestSession`で管理
- 初回訪問時にA/Bどちらかのバリアントに自動振り分け
- コンバージョン達成時にフラグ更新

### 3. 日次サマリー生成
- 毎日のイベント数を集計
- バリアント別のパフォーマンス計算
- `ABTestSummary`テーブルに保存

## 主要な機能

### フィルタリング
- **バリアント別**: A/B個別の結果確認
- **日付別**: 特定期間のパフォーマンス確認

### アクション
- **選択した日付のサマリーを再生成**: データの再集計
- **CSVエクスポート**: データの外部分析用

### 並び替え
- 日付順、コンバージョン率順などで並び替え可能

## 分析のポイント

### 1. コンバージョン率の比較
```
Variant A: 3.2%
Variant B: 4.8%
```
→ Variant Bの方が1.6ポイント高く、統計的に有意な差があれば採用検討

### 2. セッション数の確認
- 十分なサンプル数があるかチェック
- 最低でも各バリアント100セッション以上推奨

### 3. 継続的な監視
- 日々の変動パターンを確認
- 曜日や時間帯による影響を分析

## トラブルシューティング

### サマリーデータが表示されない
1. まず手動でサマリーを生成
```bash
python manage.py generate_ab_test_summary
```

2. イベントデータの確認
- ABTestEventテーブルにデータがあるか確認
- フロントエンドからのトラッキングが正常に動作しているか

### 統計が正確でない
1. サマリーの再生成
```bash
# 特定日付を再生成
python manage.py generate_ab_test_summary --date 2025-08-21
```

2. 重複データの確認
- 同一セッションの重複イベントがないか確認

## データの定期メンテナンス

### 古いデータの削除
```python
# 90日より古いイベントデータを削除（例）
from datetime import datetime, timedelta
from ab_test.models import ABTestEvent

cutoff_date = datetime.now() - timedelta(days=90)
ABTestEvent.objects.filter(created_at__lt=cutoff_date).delete()
```

### バックアップ
```bash
# サマリーデータのCSVエクスポート
python manage.py dumpdata ab_test.ABTestSummary --format=json > backup.json
```

## よくある質問

**Q: コンバージョン率が0%と表示される**
A: イベントは記録されているがコンバージョンイベントが送信されていない可能性があります。会員登録完了時のトラッキング設定を確認してください。

**Q: A/B振り分けの比率を変更したい**
A: フロントエンドの`abTestTracker.js`でバリアント振り分けロジックを調整してください。

**Q: 特定期間だけテストを実施したい**
A: 管理画面でABTestSessionの期間を指定してフィルタリングできます。

## 関連ファイル
- モデル: `/ab_test/models.py`
- 管理画面: `/ab_test/admin.py`  
- サマリー生成: `/ab_test/management/commands/generate_ab_test_summary.py`
- フロントエンド: `/src/utils/abTestTracker.js`