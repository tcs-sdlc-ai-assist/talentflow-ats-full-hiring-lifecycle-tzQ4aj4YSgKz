from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class SkillInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CandidateCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    resume_text: Optional[str] = None
    skills: Optional[list[str]] = None

    @field_validator("first_name")
    @classmethod
    def first_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("first_name must not be empty")
        if len(v) > 64:
            raise ValueError("first_name must be at most 64 characters")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("last_name must not be empty")
        if len(v) > 64:
            raise ValueError("last_name must be at most 64 characters")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("phone must be at most 20 characters")
        import re
        if not re.match(r"^[\d\s\-\+\(\)]+$", v):
            raise ValueError("phone must contain only digits, spaces, hyphens, plus signs, and parentheses")
        return v

    @field_validator("linkedin_url")
    @classmethod
    def linkedin_url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 255:
            raise ValueError("linkedin_url must be at most 255 characters")
        return v

    @field_validator("skills")
    @classmethod
    def skills_valid(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        cleaned: list[str] = []
        for skill in v:
            s = skill.strip()
            if s:
                if len(s) > 50:
                    raise ValueError(f"Skill name '{s}' must be at most 50 characters")
                cleaned.append(s)
        return cleaned if cleaned else None


class CandidateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    resume_text: Optional[str] = None
    skills: Optional[list[str]] = None

    @field_validator("first_name")
    @classmethod
    def first_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("first_name must not be empty")
        if len(v) > 64:
            raise ValueError("first_name must be at most 64 characters")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("last_name must not be empty")
        if len(v) > 64:
            raise ValueError("last_name must be at most 64 characters")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("phone must be at most 20 characters")
        import re
        if not re.match(r"^[\d\s\-\+\(\)]+$", v):
            raise ValueError("phone must contain only digits, spaces, hyphens, plus signs, and parentheses")
        return v

    @field_validator("linkedin_url")
    @classmethod
    def linkedin_url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 255:
            raise ValueError("linkedin_url must be at most 255 characters")
        return v

    @field_validator("skills")
    @classmethod
    def skills_valid(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        cleaned: list[str] = []
        for skill in v:
            s = skill.strip()
            if s:
                if len(s) > 50:
                    raise ValueError(f"Skill name '{s}' must be at most 50 characters")
                cleaned.append(s)
        return cleaned if cleaned else None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    resume_text: Optional[str] = None
    skills: list[SkillInfo] = []
    created_at: datetime


class CandidateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CandidateResponse]
    total: int
    page: int
    page_size: int