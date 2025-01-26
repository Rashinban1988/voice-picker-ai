from pydantic import BaseModel, Field, field_validator
import re

class UserCreate(BaseModel):
    sei: str = Field(..., title="姓")
    mei: str = Field(..., title="名")
    email: str = Field(..., title="メールアドレス")
    password: str = Field(..., title="パスワード")
    phone_number: str = Field(..., title="電話番号")

    @field_validator('email')
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', v):
            raise ValueError('無効なメールアドレスです')
        return v
