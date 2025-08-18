from pydantic import BaseModel, Field, field_validator
from member_management.models import User
import re

class UserCreateData(BaseModel):
    last_name: str = Field(..., title="姓")
    first_name: str = Field(..., title="名")
    email: str = Field(..., title="メールアドレス")
    password: str = Field(..., title="パスワード")
    phone_number: str = Field(..., title="電話番号")

    # キャンペーントラッキング用フィールド（オプション）
    utm_source: str | None = Field(None, title="UTMソース")
    utm_medium: str | None = Field(None, title="UTMメディウム")
    utm_campaign: str | None = Field(None, title="UTMキャンペーン")
    campaign_session_id: str | None = Field(None, title="キャンペーンセッションID")

    @field_validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', v):
            raise ValueError('無効なメールアドレスです')
        if User.objects.filter(email=v).exists():
            raise ValueError('メールアドレスが既に存在します')
        return v

    @field_validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^[0-9]{10,11}$', v):
            raise ValueError('無効な電話番号です')
        return v

    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('パスワードは8文字以上である必要があります')
        return v
