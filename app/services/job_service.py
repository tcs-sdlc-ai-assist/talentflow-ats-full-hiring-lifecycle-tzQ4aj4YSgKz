import logging
import math
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import Job
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobFilterParams,
    JobUpdate,
)

logger = logging.getLogger(__name__)

VALID_STATUSES = {"Draft", "Open", "Closed", "On Hold", "Cancelled"}

ALLOWED_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "Draft": ["Open", "Cancelled"],
    "Open": ["Closed", "On Hold", "Cancelled"],
    "Closed": ["Open", "Draft"],
    "On Hold": ["Open", "Closed", "Cancelled"],
    "Cancelled": ["Draft"],
}


class JobService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_job(self, job_data: JobCreate) -> Job:
        manager = await self.db.get(User, job_data.hiring_manager_id)
        if manager is None:
            raise ValueError(f"Hiring manager with id {job_data.hiring_manager_id} not found")

        job = Job(
            title=job_data.title,
            description=job_data.description,
            department=job_data.department,
            location=job_data.location,
            salary_range=job_data.salary_range,
            hiring_manager_id=job_data.hiring_manager_id,
            status="Draft",
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        logger.info("Created job id=%d title='%s'", job.id, job.title)
        return job

    async def get_job(self, job_id: int) -> Optional[Job]:
        stmt = (
            select(Job)
            .where(Job.id == job_id)
            .options(selectinload(Job.hiring_manager), selectinload(Job.applications))
        )
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        return job

    async def update_job(self, job_id: int, job_data: JobUpdate) -> Optional[Job]:
        job = await self.get_job(job_id)
        if job is None:
            return None

        update_fields = job_data.model_dump(exclude_unset=True, exclude_none=True)

        if "hiring_manager_id" in update_fields:
            manager = await self.db.get(User, update_fields["hiring_manager_id"])
            if manager is None:
                raise ValueError(
                    f"Hiring manager with id {update_fields['hiring_manager_id']} not found"
                )

        for field, value in update_fields.items():
            setattr(job, field, value)

        await self.db.flush()
        await self.db.refresh(job)
        logger.info("Updated job id=%d", job.id)
        return job

    async def change_status(self, job_id: int, new_status: str) -> Optional[Job]:
        if new_status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )

        job = await self.get_job(job_id)
        if job is None:
            return None

        current_status = job.status
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none'}"
            )

        job.status = new_status
        await self.db.flush()
        await self.db.refresh(job)
        logger.info(
            "Changed job id=%d status from '%s' to '%s'",
            job.id,
            current_status,
            new_status,
        )
        return job

    async def list_jobs(
        self, filters: Optional[JobFilterParams] = None
    ) -> dict:
        if filters is None:
            filters = JobFilterParams()

        stmt = select(Job).options(selectinload(Job.hiring_manager))
        count_stmt = select(func.count()).select_from(Job)

        conditions = []

        if filters.status:
            conditions.append(Job.status == filters.status)

        if filters.department:
            conditions.append(Job.department.ilike(f"%{filters.department}%"))

        if filters.location:
            conditions.append(Job.location.ilike(f"%{filters.location}%"))

        if filters.hiring_manager_id:
            conditions.append(Job.hiring_manager_id == filters.hiring_manager_id)

        if filters.search:
            search_term = f"%{filters.search}%"
            conditions.append(
                or_(
                    Job.title.ilike(search_term),
                    Job.description.ilike(search_term),
                )
            )

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        total_pages = max(1, math.ceil(total / filters.page_size))

        offset = (filters.page - 1) * filters.page_size
        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(filters.page_size)

        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())

        return {
            "items": jobs,
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
            "total_pages": total_pages,
        }

    async def list_published_jobs(self) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.status == "Open")
            .options(selectinload(Job.hiring_manager))
            .order_by(Job.created_at.desc())
        )
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())
        return jobs

    async def list_jobs_by_manager(self, manager_id: int) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.hiring_manager_id == manager_id)
            .options(selectinload(Job.hiring_manager), selectinload(Job.applications))
            .order_by(Job.created_at.desc())
        )
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())
        return jobs

    async def count_open_jobs(self, hiring_manager_id: Optional[int] = None) -> int:
        stmt = select(func.count()).select_from(Job).where(Job.status == "Open")
        if hiring_manager_id is not None:
            stmt = stmt.where(Job.hiring_manager_id == hiring_manager_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_all_jobs_brief(self) -> list[Job]:
        stmt = (
            select(Job)
            .options(selectinload(Job.hiring_manager))
            .order_by(Job.created_at.desc())
        )
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())
        return jobs