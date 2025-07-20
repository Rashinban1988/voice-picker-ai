# Ubuntu 12GBメモリ環境での最適化ガイド

## システム要件
- Ubuntu 20.04 LTS以上
- メモリ: 12GB
- Swap: 4GB推奨

## 1. Docker設定の最適化

### docker-compose.yaml の変更
```yaml
django:
  mem_limit: 3g
  memswap_limit: 3g

celery:
  command: celery -A config worker --loglevel=info --concurrency=2 --max-memory-per-child=2000000
  mem_limit: 4g
  memswap_limit: 4g

redis:
  command: redis-server --appendonly yes --maxmemory 1g --maxmemory-policy allkeys-lru
  mem_limit: 1.5g
  memswap_limit: 1.5g

zoom_bot_server:
  mem_limit: 2g
  memswap_limit: 2g
```

## 2. システム設定

### Swapの設定
```bash
# 4GB Swapファイルを作成
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Swappinessを調整（推奨: 10）
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
```

### カーネルパラメータの最適化
```bash
# /etc/sysctl.conf に追加
vm.overcommit_memory = 1
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

## 3. FFmpegの最適化

### メモリ効率的なエンコード設定
- `-preset veryfast` を使用（既に設定済み）
- 並列処理を1に制限（実装済み）
- バッファサイズを適切に設定

## 4. 監視とメンテナンス

### メモリ監視スクリプトの設定
```bash
# scripts/monitor_memory.sh を実行権限付きで設定
chmod +x scripts/monitor_memory.sh

# systemdサービスとして登録（推奨）
sudo nano /etc/systemd/system/memory-monitor.service
```

### systemdサービスファイル内容
```ini
[Unit]
Description=Memory Monitor for Voice Picker
After=docker.service

[Service]
Type=simple
ExecStart=/path/to/scripts/monitor_memory.sh
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
```

### サービスの有効化
```bash
sudo systemctl enable memory-monitor
sudo systemctl start memory-monitor
```

## 5. 定期的なメンテナンス

### Cron設定（毎日3:00にCeleryワーカー再起動）
```bash
0 3 * * * docker restart macching_app-celery-1
```

## 6. パフォーマンスチューニング

### PostgreSQL設定（使用している場合）
```sql
-- postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

### Redis設定
```conf
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## 7. トラブルシューティング

### メモリ不足時の症状
- Celeryワーカーが応答しない
- FFmpegプロセスがkillされる
- `Cannot allocate memory` エラー

### 対処法
1. 不要なサービスを停止
2. Swapを増やす
3. ワーカー数を減らす
4. 処理を時間帯で分散

## 8. 推奨事項

### 最小構成での運用
- Celeryワーカー: 1プロセス
- FFmpeg並列処理: なし
- 不要なサービス: 停止

### 将来的なアップグレード
- メモリ8GB以上を推奨
- SSDの使用を推奨
- 専用サーバーでの運用を検討