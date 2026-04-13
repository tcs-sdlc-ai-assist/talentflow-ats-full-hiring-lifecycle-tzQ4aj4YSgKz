import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from starlette.templating import Jinja2Templates

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.middleware.auth_middleware import (
    get_current_user,
    require_admin_recruiter_or_hiring_manager,
    require_any_role,
    require_interviewer,
)
from app.models.application import Application
from app.models.interview import Interview
from app.models.user import User
from app.services.interview_service import InterviewService
from app.services.audit_service import AuditTrailService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/interviews")
async def list_interviews(
    request: Request,
    application_id: Optional[int] = Query(None),
    interviewer_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    service = InterviewService(db)
    interviews_list, total = await service.list_interviews(
        application_id=application_id,
        interviewer_id=interviewer_id,
        page=page,
        page_size=page_size,
    )

    enriched_interviews = []
    for interview in interviews_list:
        interviewer_name = None
        if interview.interviewer:
            interviewer_name = interview.interviewer.full_name
        enriched = _InterviewDisplay(
            id=interview.id,
            application_id=interview.application_id,
            interviewer_id=interview.interviewer_id,
            scheduled_at=interview.scheduled_at,
            feedback_rating=interview.feedback_rating,
            feedback_notes=interview.feedback_notes,
            feedback_submitted_at=interview.feedback_submitted_at,
            created_at=interview.created_at,
            interviewer_name=interviewer_name,
        )
        enriched_interviews.append(enriched)

    return templates.TemplateResponse(
        request,
        "interviews/list.html",
        context={
            "user": current_user,
            "interviews": enriched_interviews,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/interviews/my")
async def my_interviews(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    service = InterviewService(db)
    interviews_list = await service.get_interviewer_queue(
        interviewer_id=current_user.id,
        pending_only=False,
    )

    enriched_interviews = []
    for interview in interviews_list:
        candidate_name = None
        job_title = None
        if interview.application:
            if interview.application.candidate:
                c = interview.application.candidate
                candidate_name = f"{c.first_name} {c.last_name}"
            if interview.application.job:
                job_title = interview.application.job.title

        enriched = _InterviewMyDisplay(
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
        enriched_interviews.append(enriched)

    return templates.TemplateResponse(
        request,
        "interviews/my.html",
        context={
            "user": current_user,
            "interviews": enriched_interviews,
        },
    )


@router.get("/interviews/schedule")
async def schedule_interview_form(
    request: Request,
    application_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_recruiter_or_hiring_manager),
):
    result = await db.execute(
        select(Application)
        .options(
            selectinload(Application.job),
            selectinload(Application.candidate),
        )
        .order_by(Application.applied_at.desc())
    )
    applications = list(result.scalars().all())

    result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    )
    interviewers = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "interviews/schedule_form.html",
        context={
            "user": current_user,
            "applications": applications,
            "interviewers": interviewers,
            "selected_application_id": application_id,
            "error": None,
        },
    )


@router.post("/interviews/schedule")
async def schedule_interview_submit(
    request: Request,
    application_id: int = Form(...),
    interviewer_id: int = Form(...),
    scheduled_at: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_recruiter_or_hiring_manager),
):
    from datetime import datetime

    try:
        scheduled_datetime = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError):
        result = await db.execute(
            select(Application)
            .options(
                selectinload(Application.job),
                selectinload(Application.candidate),
            )
            .order_by(Application.applied_at.desc())
        )
        applications = list(result.scalars().all())

        result = await db.execute(
            select(User).where(User.is_active == True).order_by(User.full_name)
        )
        interviewers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": current_user,
                "applications": applications,
                "interviewers": interviewers,
                "selected_application_id": application_id,
                "error": "Invalid date/time format. Please use a valid date and time.",
            },
            status_code=400,
        )

    service = InterviewService(db)
    try:
        interview = await service.schedule_interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_datetime,
        )

        audit_service = AuditTrailService(db)
        await audit_service.log_action(
            user_id=current_user.id,
            action="create",
            entity_type="Interview",
            entity_id=interview.id,
            details=f"Scheduled interview for application #{application_id} with interviewer #{interviewer_id} at {scheduled_datetime.isoformat()}",
        )

        return RedirectResponse(
            url=f"/interviews/{interview.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as e:
        result = await db.execute(
            select(Application)
            .options(
                selectinload(Application.job),
                selectinload(Application.candidate),
            )
            .order_by(Application.applied_at.desc())
        )
        applications = list(result.scalars().all())

        result = await db.execute(
            select(User).where(User.is_active == True).order_by(User.full_name)
        )
        interviewers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "interviews/schedule_form.html",
            context={
                "user": current_user,
                "applications": applications,
                "interviewers": interviewers,
                "selected_application_id": application_id,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/interviews/{interview_id}")
async def interview_detail(
    request: Request,
    interview_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    service = InterviewService(db)
    interview = await service.get_interview(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": None,
                "candidate": None,
                "job": None,
                "error": f"Interview with id {interview_id} not found.",
            },
            status_code=404,
        )

    candidate = None
    job = None
    if interview.application:
        if interview.application.candidate:
            candidate = interview.application.candidate
        if interview.application.job:
            job = interview.application.job

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": current_user,
            "interview": interview,
            "candidate": candidate,
            "job": job,
            "error": None,
            "form_data": None,
        },
    )


@router.get("/interviews/{interview_id}/feedback")
async def feedback_form(
    request: Request,
    interview_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    service = InterviewService(db)
    interview = await service.get_interview(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": None,
                "candidate": None,
                "job": None,
                "error": f"Interview with id {interview_id} not found.",
            },
            status_code=404,
        )

    candidate = None
    job = None
    if interview.application:
        if interview.application.candidate:
            candidate = interview.application.candidate
        if interview.application.job:
            job = interview.application.job

    return templates.TemplateResponse(
        request,
        "interviews/feedback_form.html",
        context={
            "user": current_user,
            "interview": interview,
            "candidate": candidate,
            "job": job,
            "error": None,
            "form_data": None,
        },
    )


@router.post("/interviews/{interview_id}/feedback")
async def submit_feedback(
    request: Request,
    interview_id: int,
    rating: int = Form(...),
    notes: Optional[str] = Form(""),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    service = InterviewService(db)
    interview = await service.get_interview(interview_id)

    if interview is None:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": None,
                "candidate": None,
                "job": None,
                "error": f"Interview with id {interview_id} not found.",
                "form_data": {"rating": rating, "notes": notes},
            },
            status_code=404,
        )

    candidate = None
    job = None
    if interview.application:
        if interview.application.candidate:
            candidate = interview.application.candidate
        if interview.application.job:
            job = interview.application.job

    try:
        updated_interview = await service.submit_feedback(
            interview_id=interview_id,
            rating=rating,
            notes=notes if notes and notes.strip() else None,
            user_id=current_user.id,
        )

        audit_service = AuditTrailService(db)
        await audit_service.log_action(
            user_id=current_user.id,
            action="update",
            entity_type="Interview",
            entity_id=interview_id,
            details=f"Submitted feedback: rating={rating}",
        )

        return RedirectResponse(
            url=f"/interviews/{interview_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except (ValueError, PermissionError) as e:
        return templates.TemplateResponse(
            request,
            "interviews/feedback_form.html",
            context={
                "user": current_user,
                "interview": interview,
                "candidate": candidate,
                "job": job,
                "error": str(e),
                "form_data": {"rating": rating, "notes": notes},
            },
            status_code=400,
        )


class _InterviewDisplay:
    def __init__(
        self,
        id,
        application_id,
        interviewer_id,
        scheduled_at,
        feedback_rating,
        feedback_notes,
        feedback_submitted_at,
        created_at,
        interviewer_name,
    ):
        self.id = id
        self.application_id = application_id
        self.interviewer_id = interviewer_id
        self.scheduled_at = scheduled_at
        self.feedback_rating = feedback_rating
        self.feedback_notes = feedback_notes
        self.feedback_submitted_at = feedback_submitted_at
        self.created_at = created_at
        self.interviewer_name = interviewer_name


class _InterviewMyDisplay:
    def __init__(
        self,
        id,
        application_id,
        interviewer_id,
        scheduled_at,
        feedback_rating,
        feedback_notes,
        feedback_submitted_at,
        created_at,
        candidate_name,
        job_title,
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