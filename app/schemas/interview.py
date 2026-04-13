from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class InterviewCreate(BaseModel):
    application_id: int
    interviewer_id: int
    scheduled_at: datetime

    @field_validator("application_id", "interviewer_id")
    @classmethod
    def must_be_positive(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return v


class FeedbackSubmit(BaseModel):
    rating: int
    notes: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_must_be_valid(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("rating must be between 1 and 5")
        return v

    @field_validator("notes")
    @classmethod
    def notes_required_for_low_rating(cls, v: Optional[str], info) -> Optional[str]:
        rating = info.data.get("rating")
        if rating is not None and rating < 3 and (v is None or v.strip() == ""):
            raise ValueError("feedback notes are required when rating is below 3")
        return v


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    interviewer_id: int
    scheduled_at: datetime
    feedback_rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    feedback_submitted_at: Optional[datetime] = None
    created_at: datetime


class InterviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[InterviewResponse]
    total: int