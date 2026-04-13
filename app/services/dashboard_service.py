import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job import Job
from app.models.user import User

logger = logging.getLogger(__name__)

APPLICATION_STAGES = [
    "Applied",
    "Screening",
    "Interview",
    "Offer",
    "Hired",
    "Rejected",
    "Withdrawn",
]


class MetricsAggregator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_open_roles(self, user: Optional[User] = None) -> int:
        query = select(func.count(Job.id)).where(Job.status == "Open")
        if user and user.role == "Hiring Manager":
            query = query.where(Job.hiring_manager_id == user.id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() or 0

    async def count_total_candidates(self) -> int:
        result = await self.db.execute(select(func.count(Candidate.id)))
        return result.scalar_one_or_none() or 0

    async def count_total_applications(self, user: Optional[User] = None) -> int:
        query = select(func.count(Application.id))
        if user and user.role == "Hiring Manager":
            query = query.join(Job, Application.job_id == Job.id).where(
                Job.hiring_manager_id == user.id
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() or 0

    async def aggregate_pipeline(self, user: Optional[User] = None) -> dict[str, int]:
        query = select(Application.status, func.count(Application.id))
        if user and user.role == "Hiring Manager":
            query = query.join(Job, Application.job_id == Job.id).where(
                Job.hiring_manager_id == user.id
            )
        query = query.group_by(Application.status)
        result = await self.db.execute(query)
        rows = result.all()

        pipeline: dict[str, int] = {}
        for stage in APPLICATION_STAGES:
            pipeline[stage] = 0
        for status, count in rows:
            pipeline[status] = count

        return pipeline

    async def count_pending_interviews(self, user: Optional[User] = None) -> int:
        query = select(func.count(Interview.id)).where(
            Interview.feedback_rating.is_(None)
        )
        if user and user.role == "Interviewer":
            query = query.where(Interview.interviewer_id == user.id)
        elif user and user.role == "Hiring Manager":
            query = query.join(
                Application, Interview.application_id == Application.id
            ).join(Job, Application.job_id == Job.id).where(
                Job.hiring_manager_id == user.id
            )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() or 0

    async def count_missing_feedback(self, user: Optional[User] = None) -> int:
        query = select(func.count(Interview.id)).where(
            Interview.feedback_rating.is_(None),
            Interview.scheduled_at < datetime.utcnow(),
        )
        if user and user.role == "Interviewer":
            query = query.where(Interview.interviewer_id == user.id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() or 0

    async def get_recent_audit_logs(self, limit: int = 10) -> list[Any]:
        query = (
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        logs = result.scalars().all()

        audit_entries = []
        for log in logs:
            entry = {
                "id": log.id,
                "timestamp": log.timestamp,
                "user_id": log.user_id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": log.details,
                "username": log.user.username if log.user else "System",
            }
            audit_entries.append(entry)

        return audit_entries

    async def get_my_jobs(self, user_id: int, limit: int = 10) -> list[Job]:
        query = (
            select(Job)
            .where(Job.hiring_manager_id == user_id)
            .where(Job.status.in_(["Open", "Draft", "On Hold"]))
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_my_interviews(self, user_id: int, limit: int = 20) -> list[Any]:
        query = (
            select(Interview)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
            )
            .where(Interview.interviewer_id == user_id)
            .order_by(Interview.scheduled_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        interviews = result.scalars().all()

        interview_entries = []
        for interview in interviews:
            candidate_name = None
            job_title = None
            if interview.application:
                if interview.application.candidate:
                    candidate = interview.application.candidate
                    candidate_name = f"{candidate.first_name} {candidate.last_name}"
                if interview.application.job:
                    job_title = interview.application.job.title

            entry_obj = _InterviewEntry(
                id=interview.id,
                application_id=interview.application_id,
                interviewer_id=interview.interviewer_id,
                scheduled_at=interview.scheduled_at,
                feedback_rating=interview.feedback_rating,
                feedback_notes=interview.feedback_notes,
                feedback_submitted_at=interview.feedback_submitted_at,
                created_at=interview.created_at,
                candidate_name=candidate_name,
                job_title=job_title,
            )
            interview_entries.append(entry_obj)

        return interview_entries


class _InterviewEntry:
    def __init__(
        self,
        id: int,
        application_id: int,
        interviewer_id: int,
        scheduled_at: Optional[datetime],
        feedback_rating: Optional[int],
        feedback_notes: Optional[str],
        feedback_submitted_at: Optional[datetime],
        created_at: Optional[datetime],
        candidate_name: Optional[str],
        job_title: Optional[str],
    ):
        self.id = id
        self.application_id = application_id
        self.interviewer_id = interviewer_id
        self.scheduled_at = scheduled_at
        self.feedback_rating = feedback_rating
        self.feedback_notes = feedback_notes
        self.feedback_submitted_at = feedback_submitted_at
        self.created_at = created_at
        self.candidate_name = candidate_name
        self.job_title = job_title


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.aggregator = MetricsAggregator(db)

    async def get_dashboard_context(self, user: User) -> dict[str, Any]:
        if user.role in ["Admin", "Recruiter"]:
            return await self._get_admin_recruiter_context(user)
        elif user.role == "Hiring Manager":
            return await self._get_hiring_manager_context(user)
        elif user.role == "Interviewer":
            return await self._get_interviewer_context(user)
        else:
            return await self._get_default_context(user)

    async def get_metrics(self, user: User) -> dict[str, Any]:
        if user.role in ["Admin", "Recruiter"]:
            return await self.get_admin_hr_metrics(user)
        elif user.role == "Hiring Manager":
            return await self.get_hiring_manager_metrics(user)
        elif user.role == "Interviewer":
            return await self.get_interviewer_metrics(user)
        else:
            return await self._get_default_metrics(user)

    async def get_admin_hr_metrics(self, user: User) -> dict[str, Any]:
        logger.info("Aggregating admin/HR metrics for user_id=%d", user.id)
        open_roles = await self.aggregator.count_open_roles()
        total_candidates = await self.aggregator.count_total_candidates()
        pending_interviews = await self.aggregator.count_pending_interviews()
        missing_feedback = await self.aggregator.count_missing_feedback()
        pipeline = await self.aggregator.aggregate_pipeline()
        total_applications = await self.aggregator.count_total_applications()

        return {
            "open_roles": open_roles,
            "total_candidates": total_candidates,
            "pending_interviews": pending_interviews,
            "missing_feedback": missing_feedback,
            "pipeline": pipeline,
            "total_applications": total_applications,
        }

    async def get_hiring_manager_metrics(self, user: User) -> dict[str, Any]:
        logger.info("Aggregating hiring manager metrics for user_id=%d", user.id)
        open_roles = await self.aggregator.count_open_roles(user)
        pending_interviews = await self.aggregator.count_pending_interviews(user)
        pipeline = await self.aggregator.aggregate_pipeline(user)
        total_applications = await self.aggregator.count_total_applications(user)

        return {
            "open_roles": open_roles,
            "pending_interviews": pending_interviews,
            "pipeline": pipeline,
            "total_applications": total_applications,
        }

    async def get_interviewer_metrics(self, user: User) -> dict[str, Any]:
        logger.info("Aggregating interviewer metrics for user_id=%d", user.id)
        pending_interviews = await self.aggregator.count_pending_interviews(user)
        missing_feedback = await self.aggregator.count_missing_feedback(user)

        return {
            "pending_interviews": pending_interviews,
            "missing_feedback": missing_feedback,
        }

    async def _get_default_metrics(self, user: User) -> dict[str, Any]:
        logger.info("Aggregating default metrics for user_id=%d", user.id)
        open_roles = await self.aggregator.count_open_roles()
        total_candidates = await self.aggregator.count_total_candidates()
        pending_interviews = await self.aggregator.count_pending_interviews()
        pipeline = await self.aggregator.aggregate_pipeline()

        return {
            "open_roles": open_roles,
            "total_candidates": total_candidates,
            "pending_interviews": pending_interviews,
            "pipeline": pipeline,
        }

    async def _get_admin_recruiter_context(self, user: User) -> dict[str, Any]:
        metrics = await self.get_admin_hr_metrics(user)
        recent_audit_logs = await self.aggregator.get_recent_audit_logs(limit=10)

        return {
            "user": user,
            "metrics": metrics,
            "recent_audit_logs": recent_audit_logs,
        }

    async def _get_hiring_manager_context(self, user: User) -> dict[str, Any]:
        metrics = await self.get_hiring_manager_metrics(user)
        my_jobs = await self.aggregator.get_my_jobs(user.id, limit=10)

        return {
            "user": user,
            "metrics": metrics,
            "my_jobs": my_jobs,
        }

    async def _get_interviewer_context(self, user: User) -> dict[str, Any]:
        metrics = await self.get_interviewer_metrics(user)
        my_interviews = await self.aggregator.get_my_interviews(user.id, limit=20)

        return {
            "user": user,
            "metrics": metrics,
            "my_interviews": my_interviews,
        }

    async def _get_default_context(self, user: User) -> dict[str, Any]:
        metrics = await self._get_default_metrics(user)

        return {
            "user": user,
            "metrics": metrics,
        }