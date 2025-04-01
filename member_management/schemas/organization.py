from pydantic import BaseModel, Field

class OrganizationCreateData(BaseModel):
    name: str = Field(..., title="組織名")
    phone_number: str = Field(..., title="電話番号")
