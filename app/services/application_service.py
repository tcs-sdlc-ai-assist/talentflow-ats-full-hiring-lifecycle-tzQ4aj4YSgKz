import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.application import (
    ALLOWED_TRANSITIONS,
    APPLICATION_STATUSES,
    ApplicationCreate,
    ApplicationStatusUpdate,
)

logger = logging.getLogger(__name__)


class ApplicationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_application(
        self,
        data: ApplicationCreate,
        user_id: Optional[int] = None,
    ) -> Application:
        job_result = await self.db.execute(
            select(Job).where(Job.id == data.job_id)
        )
        job = job_result.scalars().first()
        if job is None:
            raise ValueError(f"Job with id {data.job_id} not found")

        candidate_result = await self.db.execute(
            select(Candidate).where(Candidate.id == data.candidate_id)
        )
        candidate = candidate_result.scalars().first()
        if candidate is None:
            raise ValueError(f"Candidate with id {data.candidate_id} not found")

        existing_result = await self.db.execute(
            select(Application).where(
                Application.job_id == data.job_id,
                Application.candidate_id == data.candidate_id,
            )
        )
        existing = existing_result.scalars().first()
        if existing is not None:
            raise ValueError(
                f"Application already exists for candidate {data.candidate_id} "
                f"and job {data.job_id}"
            )

        application = Application(
            job_id=data.job_id,
            candidate_id=data.candidate_id,
            status="Applied",
        )
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "Application created: id=%d, job_id=%d, candidate_id=%d, user_id=%s",
            application.id,
            application.job_id,
            application.candidate_id,
            user_id,
        )
        return application

    async def update_status(
        self,
        application_id: int,
        new_status: str,
        user_id: Optional[int] = None,
    ) -> Application:
        if new_status not in APPLICATION_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. "
                f"Must be one of: {', '.join(APPLICATION_STATUSES)}"
            )

        result = await self.db.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.job),
                selectinload(Application.candidate),
                selectinload(Application.interviews),
            )
        )
        application = result.scalars().first()
        if application is None:
            raise ValueError(f"Application with id {application_id} not found")

        current_status = application.status
        allowed = ALLOWED_TRANSITIONS.get(current_status, [])

        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none (terminal state)'}"
            )

        application.status = new_status
        application.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(application)

        logger.info(
            "Application %d status updated: %s -> %s by user_id=%s",
            application_id,
            current_status,
            new_status,
            user_id,
        )
        return application

    async def get_application(self, application_id: int) -> Optional[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.job),
                selectinload(Application.candidate),
                selectinload(Application.interviews),
            )
        )
        application = result.scalars().first()
        return application

    async def list_applications(
        self,
        status: Optional[str] = None,
        job_id: Optional[int] = None,
        candidate_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        query = select(Application).options(
            selectinload(Application.job),
            selectinload(Application.candidate),
            selectinload(Application.interviews),
        )

        count_query = select(func.count(Application.id))

        if status is not None and status != "":
            query = query.where(Application.status == status)
            count_query = count_query.where(Application.status == status)

        if job_id is not None:
            query = query.where(Application.job_id == job_id)
            count_query = count_query.where(Application.job_id == job_id)

        if candidate_id is not None:
            query = query.where(Application.candidate_id == candidate_id)
            count_query = count_query.where(Application.candidate_id == candidate_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Application.applied_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        applications = list(result.scalars().all())

        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return {
            "items": applications,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def kanban_view(
        self,
        job_id: Optional[int] = None,
    ) -> dict[str, list[Application]]:
        stages = ["Applied", "Screening", "Interview", "Offer", "Hired", "Rejected"]

        columns: dict[str, list[Application]] = {stage: [] for stage in stages}

        query = select(Application).options(
            selectinload(Application.job),
            selectinload(Application.candidate),
            selectinload(Application.interviews),
        )

        if job_id is not None:
            query = query.where(Application.job_id == job_id)

        query = query.order_by(Application.applied_at.asc())

        result = await self.db.execute(query)
        applications = result.scalars().all()

        for application in applications:
            status = application.status
            if status in columns:
                columns[status].append(application)
            elif status == "Withdrawn":
                pass
            else:
                logger.warning(
                    "Application %d has unexpected status '%s'",
                    application.id,
                    status,
                )

        return columns

    async def get_applications_for_candidate(
        self,
        candidate_id: int,
    ) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .options(
                selectinload(Application.job),
                selectinload(Application.candidate),
                selectinload(Application.interviews),
            )
            .order_by(Application.applied_at.desc())
        )
        return list(result.scalars().all())

    async def get_applications_for_job(
        self,
        job_id: int,
    ) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.job_id == job_id)
            .options(
                selectinload(Application.job),
                selectinload(Application.candidate),
                selectinload(Application.interviews),
            )
            .order_by(Application.applied_at.desc())
        )
        return list(result.scalars().all())