# Celeryワーカー操作ガイド

## 基本的なワーカー操作

### 1. ワーカーの状態確認
```bash
# ワーカーが動いているか確認
docker ps | grep celery

# ワーカーのログを確認
docker logs macching_app-celery-1 --tail 20

# リアルタイムでログを監視
docker logs -f macching_app-celery-1
```

### 2. ワーカーの制御
```bash
# ワーカーを再起動（推奨：詰まったタスクをクリア）
docker restart macching_app-celery-1

# ワーカーを停止
docker stop macching_app-celery-1

# ワーカーを開始
docker start macching_app-celery-1
```

### 3. タスクの監視
```bash
# アクティブなタスクを確認
docker exec macching_app-celery-1 celery -A config inspect active

# 予約されたタスクを確認
docker exec macching_app-celery-1 celery -A config inspect reserved

# ワーカーの統計情報
docker exec macching_app-celery-1 celery -A config inspect stats
```

### 4. キューの管理
```bash
# 全てのタスクを削除（緊急時）
docker exec macching_app-celery-1 celery -A config purge

# 特定のタスクをキャンセル
docker exec macching_app-celery-1 celery -A config control revoke <task_id>

# Redis内のキューを確認
docker exec macching_app-redis-1 redis-cli LLEN celery
```

## トラブルシューティング

### よくある問題と解決法

#### 1. タスクが詰まっている
```bash
docker restart macching_app-celery-1
```

#### 2. ワーカーが応答しない
```bash
docker logs macching_app-celery-1 --tail 50
# エラーを確認後、再起動
docker restart macching_app-celery-1
```

#### 3. メモリ不足
```bash
# コンテナのリソース使用量確認
docker stats macching_app-celery-1
```

#### 4. 削除されたファイルに対するタスクが残っている
```bash
# 全タスクをパージ（失敗タスクもクリア）
docker exec macching_app-celery-1 celery -A config purge

# ワーカーを再起動
docker restart macching_app-celery-1
```

#### 5. 特定のタスクが無限リトライしている
```bash
# 特定タスクをキャンセル
docker exec macching_app-celery-1 celery -A config control revoke <task_id> --terminate

# または全タスクをパージ
docker exec macching_app-celery-1 celery -A config purge
```

### 完全リセット手順

削除されたファイルに対するタスクが残っている場合の完全リセット：

```bash
# 1. 全タスクをパージ
docker exec macching_app-celery-1 celery -A config purge

# 2. ワーカーを再起動
docker restart macching_app-celery-1

# 3. Redis内のキューもクリア（必要に応じて）
docker exec macching_app-redis-1 redis-cli FLUSHDB
```

### 推奨される定期メンテナンス

```bash
# 週1回程度：ワーカーを再起動してメモリをクリア
docker restart macching_app-celery-1

# 必要に応じて：古いタスクをパージ
docker exec macching_app-celery-1 celery -A config purge
```

## エラーパターンと対処法

### UploadedFile matching query does not exist
- **原因**: データベースから削除されたファイルに対するタスクが残っている
- **対処**: 全タスクをパージしてワーカーを再起動

### NVENC hardware encoder errors
- **原因**: Docker環境でGPUアクセスができない
- **対処**: 既に実装済み（ソフトウェアエンコーディングに自動フォールバック）

### Task timeout errors
- **原因**: 大きなファイルの処理時間が長すぎる
- **対処**: タスクのタイムアウト設定を調整するか、ファイルサイズ制限を設ける

## コード変更時の再起動

### 🔄 再起動が必要な変更
- **タスク関数の修正** (`tasks.py`)
- **インポートするモジュールの変更**
- **設定ファイルの変更**
- **新しい関数やクラスの追加**

### ⚡ 再起動不要な変更
- **データベースの変更**
- **静的ファイルの変更**
- **フロントエンドの変更**
- **テンプレートファイルの変更**

### 変更を反映させる方法

#### 通常の再起動
```bash
# Celeryワーカーを再起動
docker restart macching_app-celery-1

# 起動確認
docker logs macching_app-celery-1 --tail 10
```

#### 開発時の自動リロード（推奨）
```bash
# docker-compose.ymlでワーカーに--reloadオプションを追加
# celery -A config worker --reload --loglevel=info
```

#### 本番環境での安全な再起動
```bash
# 現在のタスクを完了させてから再起動
docker exec macching_app-celery-1 celery -A config control shutdown
docker start macching_app-celery-1
```

## 監視とログ

### 重要なログレベル
- `INFO`: 正常な処理フロー
- `WARNING`: 警告（処理は継続）
- `ERROR`: エラー（処理失敗、リトライの可能性あり）

### よく確認するログパターン
```bash
# HLS変換の進行状況
docker logs macching_app-celery-1 | grep "HLS generation"

# 文字起こしの進行状況
docker logs macching_app-celery-1 | grep "transcription"

# AI分析の進行状況
docker logs macching_app-celery-1 | grep "AI analysis"

# エラーのみ表示
docker logs macching_app-celery-1 | grep "ERROR"

# 特定のファイルの処理を追跡
docker logs macching_app-celery-1 | grep "uploaded_file_id: <FILE_ID>"
```

## 処理フローの理解

### 完全な自動処理フロー
```
ファイルアップロード
    ↓
文字起こしタスク (transcribe_and_save_async)
    ↓
AI分析タスク (generate_ai_analysis_async) ← 自動キューイング
    ├── 要約生成 (summarize_text)
    ├── 課題特定 (definition_issue) 
    └── 取り組み案生成 (definition_solution)
    ↓
HLS変換タスク (generate_hls_async) ← 動画の場合のみ
```

### 各タスクで確認すべきログ
1. **文字起こし**: `"Transcription completed successfully"`
2. **AI分析**: `"AI analysis completed successfully"`
3. **HLS変換**: `"HLS generation completed"`