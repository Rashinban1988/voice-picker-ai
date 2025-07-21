#!/bin/bash
# Django静的ファイルセットアップスクリプト

echo "=== Django静的ファイルセットアップ ==="

# 1. collectstaticの実行
echo "1. 静的ファイルを収集中..."
docker compose exec django python manage.py collectstatic --noinput --clear

# 2. パーミッションの設定
echo "2. パーミッションを設定中..."
# Nginxがアクセスできるようにパーミッションを設定
chmod -R 755 /home/vpi/django-app/staticfiles/
chmod -R 755 /home/vpi/django-app/media/

# 3. 所有者の確認（必要に応じて変更）
echo "3. ディレクトリ情報:"
ls -la /home/vpi/django-app/staticfiles/
ls -la /home/vpi/django-app/media/

echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "1. Nginx設定を更新: sudo cp /home/vpi/django-app/nginx_server_config.conf /etc/nginx/sites-enabled/django.voice-picker-ai.com"
echo "2. Nginx設定をテスト: sudo nginx -t"
echo "3. Nginxをリロード: sudo systemctl reload nginx"