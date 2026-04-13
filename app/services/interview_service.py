import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interview import Interview
from app.models.application import Application
from app.models.user import User

logger = logging.getLogger(__name__)


class InterviewService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def schedule_interview(
        self,
        application_id: int,
        interviewer_id: int,
        scheduled_at: datetime,
    ) -> Interview:
        result = await self.db.execute(
            select(Application).where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise ValueError(f"Application with id {application_id} not found")

        result = await self.db.execute(
            select(User).where(User.id == interviewer_id, User.is_active == True)
        )
        interviewer = result.scalar_one_or_none()
        if interviewer is None:
            raise ValueError(f"Interviewer with id {interviewer_id} not found or inactive")

        interview = Interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_at,
        )
        self.db.add(interview)
        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "Scheduled interview id=%d for application_id=%d with interviewer_id=%d at %s",
            interview.id,
            application_id,
            interviewer_id,
            scheduled_at.isoformat(),
        )
        return interview

    async def submit_feedback(
        self,
        interview_id: int,
        rating: int,
        notes: Optional[str],
        user_id: int,
    ) -> Interview:
        result = await self.db.execute(
            select(Interview).where(Interview.id == interview_id)
        )
        interview = result.scalar_one_or_none()
        if interview is None:
            raise ValueError(f"Interview with id {interview_id} not found")

        if interview.interviewer_id != user_id:
            raise PermissionError("Only the assigned interviewer can submit feedback")

        if interview.feedback_submitted_at is not None:
            raise ValueError("Feedback has already been submitted for this interview")

        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        if rating < 3 and (notes is None or notes.strip() == ""):
            raise ValueError("Feedback notes are required when rating is below 3")

        interview.feedback_rating = rating
        interview.feedback_notes = notes
        interview.feedback_submitted_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(interview)

        logger.info(
            "Feedback submitted for interview id=%d by user_id=%d, rating=%d",
            interview_id,
            user_id,
            rating,
        )
        return interview

    async def get_interview(self, interview_id: int) -> Optional[Interview]:
        result = await self.db.execute(
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.application),
                selectinload(Interview.interviewer),
            )
        )
        return result.scalar_one_or_none()

    async def list_interviews(
        self,
        application_id: Optional[int] = None,
        interviewer_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Interview], int]:
        query = select(Interview).options(
            selectinload(Interview.application),
            selectinload(Interview.interviewer),
        )
        count_query = select(func.count()).select_from(Interview)

        if application_id is not None:
            query = query.where(Interview.application_id == application_id)
            count_query = count_query.where(Interview.application_id == application_id)

        if interviewer_id is not None:
            query = query.where(Interview.interviewer_id == interviewer_id)
            count_query = count_query.where(Interview.interviewer_id == interviewer_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Interview.scheduled_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        interviews = list(result.scalars().all())

        return interviews, total

    async def get_interviewer_queue(
        self,
        interviewer_id: int,
        pending_only: bool = False,
    ) -> list[Interview]:
        query = (
            select(Interview)
            .where(Interview.interviewer_id == interviewer_id)
            .options(
                selectinload(Interview.application),
                selectinload(Interview.interviewer),
            )
        )

        if pending_only:
            query = query.where(Interview.feedback_submitted_at.is_(None))

        query = query.order_by(Interview.scheduled_at.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_pending_feedback_count(self, interviewer_id: int) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Interview)
            .where(
                Interview.interviewer_id == interviewer_id,
                Interview.feedback_submitted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def get_interviews_for_application(self, application_id: int) -> list[Interview]:
        result = await self.db.execute(
            select(Interview)
            .where(Interview.application_id == application_id)
            .options(
                selectinload(Interview.application),
                selectinload(Interview.interviewer),
            )
            .order_by(Interview.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def count_pending_interviews(self) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Interview)
            .where(Interview.feedback_submitted_at.is_(None))
        )
        return result.scalar() or 0

    async def count_missing_feedback(self, interviewer_id: Optional[int] = None) -> int:
        query = (
            select(func.count())
            .select_from(Interview)
            .where(
                Interview.feedback_submitted_at.is_(None),
                Interview.scheduled_at < datetime.utcnow(),
            )
        )
        if interviewer_id is not None:
            query = query.where(Interview.interviewer_id == interviewer_id)

        result = await self.db.execute(query)
        return result.scalar() or 0