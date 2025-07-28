# A/Bテスト実装のセキュリティ推奨事項

## 現在の実装の安全性

### ✅ 既に安全な部分
1. **入力検証**: バリアント値とイベントタイプは厳密に検証
2. **SQLインジェクション対策**: Django ORMによる自動エスケープ
3. **CSRF対策**: DjangoのCSRF保護機能が有効

### ⚠️ 推奨される追加のセキュリティ対策

## 1. レート制限の実装

```python
# settings.py に追加
INSTALLED_APPS = [
    # ...
    'django_ratelimit',
]

# views.py の修正例
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

@method_decorator(ratelimit(key='ip', rate='100/h', method='POST'), name='post')
class ABTestTrackView(APIView):
    # 既存のコード
```

## 2. ユーザーIDのハッシュ化

```python
# utils.py を作成
import hashlib
from django.conf import settings

def hash_user_id(user_id: str) -> str:
    """ユーザーIDをハッシュ化"""
    salt = settings.SECRET_KEY
    return hashlib.sha256(f"{salt}{user_id}".encode()).hexdigest()[:16]
```

## 3. 統計APIへのアクセス制限

```python
# views.py の修正
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class ABTestStatsView(APIView):
    permission_classes = [IsAuthenticated]  # または IsAdminUser
```

## 4. セッションIDの検証強化

```python
# serializers.py に追加
def validate_session_id(self, value):
    """セッションIDの形式を検証"""
    import re
    pattern = r'^session_\d+_[a-z0-9]{9}$'
    if not re.match(pattern, value):
        raise serializers.ValidationError('Invalid session ID format')
    return value
```

## 5. CORS設定の厳密化（本番環境）

```python
# settings.py
if not DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "https://voice-picker-ai.com",
        "https://www.voice-picker-ai.com",
    ]
    CORS_ALLOW_ALL_ORIGINS = False
```

## 6. ログの適切な管理

```python
# ユーザーIDをログに記録する際は必ずハッシュ化
logger.info(f'Conversion tracked for user: {hash_user_id(user_id)}')
```

## 7. データ保持ポリシー

```python
# 古いA/Bテストデータを定期的に削除
# management/commands/cleanup_ab_test_data.py
from datetime import timedelta
from django.utils import timezone

def cleanup_old_data():
    cutoff_date = timezone.now() - timedelta(days=90)
    ABTestEvent.objects.filter(created_at__lt=cutoff_date).delete()
```

## まとめ

現在の実装は基本的なセキュリティ要件を満たしていますが、本番環境では以下を推奨：

1. **必須**: レート制限の実装
2. **推奨**: ユーザーIDのハッシュ化
3. **推奨**: 統計APIへのアクセス制限
4. **オプション**: より厳密な入力検証

これらの対策により、より堅牢なA/Bテストシステムを構築できます。