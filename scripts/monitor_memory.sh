#!/bin/bash
# メモリ使用状況を監視し、閾値を超えたらCeleryを再起動

THRESHOLD=85  # メモリ使用率の閾値（%）

while true; do
    # メモリ使用率を取得
    MEMORY_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')

    echo "[$(date)] Memory usage: ${MEMORY_USAGE}%"

    if [ $MEMORY_USAGE -gt $THRESHOLD ]; then
        echo "[$(date)] Memory usage exceeded ${THRESHOLD}%. Restarting Celery..."
        docker restart macching_app-celery-1
        # 再起動後は5分待機
        sleep 300
    fi

    # 30秒ごとにチェック
    sleep 30
done