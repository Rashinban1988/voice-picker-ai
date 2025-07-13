#!/usr/bin/env python
"""
Webhook統合テスト実行スクリプト
Django管理コマンドを使わずに直接テストを実行
"""

import os
import sys
import django
from pathlib import Path

# プロジェクトのパスを追加
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# 環境変数を設定
if os.path.exists('.env.test'):
    with open('.env.test', 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'macching_app.settings.minimal_test')
django.setup()

# テストの実行
if __name__ == "__main__":
    print("🎣 Webhook統合テスト開始")
    print("=" * 50)

    try:
        # データベースマイグレーション
        print("📊 データベースマイグレーション実行中...")
        from django.core.management import execute_from_command_line
        import sys

        # マイグレーションを実行
        sys.argv = ['manage.py', 'migrate', '--run-syncdb']
        execute_from_command_line(sys.argv)

        # テストクラスをインポート
        from tests.integration.test_stripe_integration import StripeWebhookIntegrationTest

        # テストインスタンスを作成
        test_instance = StripeWebhookIntegrationTest()

        # セットアップを実行
        print("🔧 テストセットアップ中...")
        test_instance.setUpClass()
        test_instance.setUp()

        # Webhookテストを実行
        print("🧪 Webhook署名検証テスト実行中...")
        test_instance.test_webhook_signature_validation()

        print("✅ Webhook統合テスト成功!")

    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # クリーンアップ
        try:
            test_instance.tearDown()
            print("🧹 テストクリーンアップ完了")
        except:
            pass

    print("=" * 50)
    print("🎯 Webhook統合テスト完了")
