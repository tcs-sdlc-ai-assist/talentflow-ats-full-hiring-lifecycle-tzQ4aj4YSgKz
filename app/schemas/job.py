from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Job title")
    description: str = Field(..., min_length=1, description="Job description")
    department: str = Field(default="", max_length=100, description="Department name")
    location: str = Field(..., min_length=1, max_length=200, description="Job location")
    salary_range: Optional[str] = Field(default=None, max_length=100, description="Salary range e.g. 120000-150000")
    hiring_manager_id: int = Field(..., gt=0, description="ID of the hiring manager (user)")


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, min_length=1)
    department: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, min_length=1, max_length=200)
    salary_range: Optional[str] = Field(default=None, max_length=100)
    hiring_manager_id: Optional[int] = Field(default=None, gt=0)


class JobStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=20, description="New job status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed_statuses = {"Draft", "Open", "Closed", "On Hold", "Cancelled"}
        if v not in allowed_statuses:
            raise ValueError(f"Invalid status '{v}'. Allowed: {', '.join(sorted(allowed_statuses))}")
        return v


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    department: str
    location: str
    salary_range: Optional[str] = None
    status: str
    hiring_manager_id: int
    created_at: datetime
    updated_at: datetime


class JobBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    department: str
    location: str
    status: str
    created_at: datetime


class PaginationMeta(BaseModel):
    total: int = Field(..., ge=0, description="Total number of records")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Number of records per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class JobListResponse(BaseModel):
    items: list[JobBriefResponse]
    pagination: PaginationMeta


class JobFilterParams(BaseModel):
    status: Optional[str] = Field(default=None, max_length=20, description="Filter by job status")
    department: Optional[str] = Field(default=None, max_length=100, description="Filter by department")
    location: Optional[str] = Field(default=None, max_length=200, description="Filter by location")
    hiring_manager_id: Optional[int] = Field(default=None, gt=0, description="Filter by hiring manager ID")
    search: Optional[str] = Field(default=None, max_length=200, description="Search in title and description")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @field_validator("status")
    @classmethod
    def validate_filter_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed_statuses = {"Draft", "Open", "Closed", "On Hold", "Cancelled"}
            if v not in allowed_statuses:
                raise ValueError(f"Invalid status filter '{v}'. Allowed: {', '.join(sorted(allowed_statuses))}")
        return v