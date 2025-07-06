#!/usr/bin/env python
"""
Stripeサブスクリプション機能のテスト実行スクリプト
"""

import os
import sys
import django
from django.conf import settings

# Djangoの設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.test_settings')
django.setup()

def run_stripe_tests():
    """Stripe関連のテストを実行"""
    from django.test.utils import get_runner
    
    # テストランナーを取得
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    
    # Stripe関連のテストのみを実行
    test_labels = [
        'member_management.tests.test_stripe',
    ]
    
    # テストを実行
    failures = test_runner.run_tests(test_labels)
    
    if failures:
        print(f"\n❌ {failures} 個のテストが失敗しました")
        sys.exit(1)
    else:
        print("\n✅ すべてのテストが成功しました")

if __name__ == '__main__':
    print("🧪 Stripeサブスクリプション機能のテストを開始します...")
    run_stripe_tests() 