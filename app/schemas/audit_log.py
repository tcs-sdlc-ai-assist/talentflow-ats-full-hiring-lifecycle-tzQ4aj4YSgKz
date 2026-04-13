from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditLogCreate(BaseModel):
    user_id: Optional[int] = None
    action: str = Field(..., max_length=500)
    entity_type: str = Field(..., max_length=100)
    entity_id: int
    details: Optional[str] = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: int
    details: Optional[str] = None
    username: Optional[str] = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)


class AuditLogFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)
    user_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    action: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    @field_validator("entity_type", mode="before")
    @classmethod
    def strip_entity_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v

    @field_validator("action", mode="before")
    @classmethod
    def strip_action(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse] = []
    total: int = 0
    page: int = 1
    per_page: int = 50
    total_pages: int = 0