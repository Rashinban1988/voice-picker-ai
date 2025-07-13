#!/usr/bin/env python3
"""
OpenAI API設定と使用状況確認スクリプト
"""

import os
import sys
from pathlib import Path

# Djangoの設定を読み込む
sys.path.append('/code')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from openai import OpenAI
from django.conf import settings
from decouple import config

def check_openai_api():
    """OpenAI APIキーと設定を確認"""

    print("=== OpenAI API 設定確認 ===")

    # 1. APIキーの確認
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY環境変数が設定されていません")
        return False

    print(f"✅ APIキー設定: {api_key[:8]}...{api_key[-4:]} (長さ: {len(api_key)})")

    # 2. OpenAIクライアントの初期化テスト
    try:
        client = OpenAI(api_key=api_key)
        print("✅ OpenAIクライアント初期化成功")
    except Exception as e:
        print(f"❌ OpenAIクライアント初期化失敗: {e}")
        return False

    # 3. APIキーの有効性テスト
    try:
        # モデル一覧を取得してAPIキーの有効性を確認
        models = client.models.list()
        print(f"✅ API接続成功 - 利用可能モデル数: {len(models.data)}")

        # Whisperモデルの確認
        whisper_models = [m for m in models.data if 'whisper' in m.id]
        if whisper_models:
            print(f"✅ Whisperモデル利用可能: {[m.id for m in whisper_models]}")
        else:
            print("⚠️  Whisperモデルが見つかりません")

    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "authentication" in error_str:
            print(f"❌ API認証エラー: APIキーが無効です - {e}")
        elif "429" in error_str or "quota" in error_str:
            print(f"❌ クォータ/レート制限エラー: {e}")
            print("💡 対処方法:")
            print("   1. OpenAIダッシュボードで使用量を確認")
            print("   2. 支払い方法が設定されているか確認")
            print("   3. 使用制限額を確認/増額")
        else:
            print(f"❌ API呼び出しエラー: {e}")
        return False

    # 4. 組織情報の確認（可能な場合）
    try:
        # 使用量情報は管理者APIでのみ取得可能
        print("✅ 基本的なAPI設定は正常です")

    except Exception as e:
        print(f"⚠️  詳細情報取得不可: {e}")

    print("\n=== 推奨対処方法 ===")
    print("1. OpenAIダッシュボード (https://platform.openai.com/) にログイン")
    print("2. Billing & Usage で使用量と制限を確認")
    print("3. Payment methods で支払い方法を確認")
    print("4. Usage limits で月額制限を確認/増額")
    print("5. API keys でキーの有効性を確認")

    return True

if __name__ == "__main__":
    check_openai_api()
