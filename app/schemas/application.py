from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


APPLICATION_STATUSES = [
    "Applied",
    "Screening",
    "Interview",
    "Offer",
    "Hired",
    "Rejected",
    "Withdrawn",
]

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "Applied": ["Screening", "Rejected", "Withdrawn"],
    "Screening": ["Interview", "Rejected", "Withdrawn"],
    "Interview": ["Offer", "Rejected", "Withdrawn"],
    "Offer": ["Hired", "Rejected", "Withdrawn"],
    "Hired": [],
    "Rejected": [],
    "Withdrawn": [],
}


class ApplicationCreate(BaseModel):
    job_id: int
    candidate_id: int

    model_config = ConfigDict(from_attributes=True)


class ApplicationStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in APPLICATION_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(APPLICATION_STATUSES)}"
            )
        return v

    model_config = ConfigDict(from_attributes=True)


class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    status: str
    applied_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)


class ApplicationKanbanColumn(BaseModel):
    status: str
    applications: list[ApplicationResponse]

    model_config = ConfigDict(from_attributes=True)


class ApplicationKanbanResponse(BaseModel):
    job_id: int
    columns: dict[str, list[ApplicationResponse]]

    model_config = ConfigDict(from_attributes=True)