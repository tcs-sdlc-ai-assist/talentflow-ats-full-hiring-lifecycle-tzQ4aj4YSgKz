from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class UserLogin(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("Username must be between 3 and 32 characters.")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("Username must contain only alphanumeric characters and underscores.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if " " in v:
            raise ValueError("Password must not contain spaces.")
        return v


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("Username must be between 3 and 32 characters.")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("Username must contain only alphanumeric characters and underscores.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if " " in v:
            raise ValueError("Password must not contain spaces.")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 64:
            raise ValueError("Full name must be between 3 and 64 characters.")
        if not all(c.isalpha() or c == " " for c in v):
            raise ValueError("Full name must contain only letters and spaces.")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str


class UserContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthResponse(BaseModel):
    success: bool
    user: Optional[UserResponse] = None
    redirect_url: Optional[str] = None
    error: Optional[str] = None