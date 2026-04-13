import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import (
    get_current_user,
    require_admin_or_recruiter,
    require_admin_recruiter_or_hiring_manager,
    require_any_role,
)
from app.models.user import User
from app.schemas.application import ALLOWED_TRANSITIONS
from app.services.application_service import ApplicationService
from app.services.audit_service import AuditTrailService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/applications")
async def list_applications(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    job_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    app_service = ApplicationService(db)
    job_service = JobService(db)

    result = await app_service.list_applications(
        status=status_filter,
        job_id=job_id,
        page=page,
        page_size=page_size,
    )

    applications = result["items"]
    total = result["total"]
    total_pages = result["total_pages"]

    enriched_applications = []
    for app in applications:
        app_dict = _enrich_application(app)
        enriched_applications.append(app_dict)

    jobs_data = await job_service.get_all_jobs_brief()

    filters = {
        "status": status_filter or "",
        "job_id": str(job_id) if job_id else "",
    }

    return templates.TemplateResponse(
        request,
        "applications/list.html",
        context={
            "user": current_user,
            "applications": enriched_applications,
            "jobs": jobs_data,
            "filters": type("Filters", (), filters),
            "total": total,
            "total_pages": total_pages,
            "page": page,
        },
    )


@router.get("/applications/pipeline")
async def pipeline_view(
    request: Request,
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    app_service = ApplicationService(db)
    job_service = JobService(db)

    columns = await app_service.kanban_view(job_id=job_id)

    enriched_columns = {}
    for stage, apps in columns.items():
        enriched_columns[stage] = []
        for app in apps:
            app_obj = _enrich_application(app)
            enriched_columns[stage].append(app_obj)

    jobs_data = await job_service.get_all_jobs_brief()

    return templates.TemplateResponse(
        request,
        "applications/pipeline.html",
        context={
            "user": current_user,
            "columns": enriched_columns,
            "jobs": jobs_data,
            "selected_job_id": job_id,
        },
    )


@router.get("/applications/create")
async def create_application_form(
    request: Request,
    job_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    job_service = JobService(db)
    from app.services.candidate_service import CandidateService

    candidate_service = CandidateService(db)

    jobs_data = await job_service.get_all_jobs_brief()
    candidates_list, _ = await candidate_service.list_candidates(page=1, page_size=1000)

    return templates.TemplateResponse(
        request,
        "applications/create.html",
        context={
            "user": current_user,
            "jobs": jobs_data,
            "candidates": candidates_list,
            "selected_job_id": job_id,
            "error": None,
        },
    )


@router.post("/applications/create")
async def create_application(
    request: Request,
    job_id: int = Form(...),
    candidate_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    from app.schemas.application import ApplicationCreate
    from app.services.candidate_service import CandidateService

    app_service = ApplicationService(db)
    audit_service = AuditTrailService(db)

    try:
        data = ApplicationCreate(job_id=job_id, candidate_id=candidate_id)
        application = await app_service.create_application(
            data=data,
            user_id=current_user.id,
        )

        await audit_service.log_action(
            user_id=current_user.id,
            action="create",
            entity_type="Application",
            entity_id=application.id,
            details=f"Created application for job_id={job_id}, candidate_id={candidate_id}",
        )

        return RedirectResponse(
            url=f"/applications/{application.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as e:
        logger.warning(
            "Failed to create application: %s (user_id=%d)", str(e), current_user.id
        )

        job_service = JobService(db)
        candidate_service = CandidateService(db)

        jobs_data = await job_service.get_all_jobs_brief()
        candidates_list, _ = await candidate_service.list_candidates(
            page=1, page_size=1000
        )

        return templates.TemplateResponse(
            request,
            "applications/create.html",
            context={
                "user": current_user,
                "jobs": jobs_data,
                "candidates": candidates_list,
                "selected_job_id": job_id,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/applications/{application_id}")
async def application_detail(
    request: Request,
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    app_service = ApplicationService(db)
    from app.services.interview_service import InterviewService

    interview_service = InterviewService(db)

    application = await app_service.get_application(application_id)
    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": current_user,
                "application": None,
                "candidate": None,
                "job": None,
                "interviews": [],
                "allowed_transitions": [],
                "error": f"Application #{application_id} not found.",
            },
            status_code=404,
        )

    candidate = application.candidate if application.candidate else None
    job = application.job if application.job else None

    interviews = await interview_service.get_interviews_for_application(application_id)

    allowed_transitions = ALLOWED_TRANSITIONS.get(application.status, [])

    return templates.TemplateResponse(
        request,
        "applications/detail.html",
        context={
            "user": current_user,
            "application": application,
            "candidate": candidate,
            "job": job,
            "interviews": interviews,
            "allowed_transitions": allowed_transitions,
        },
    )


@router.post("/applications/{application_id}/status")
async def update_application_status(
    request: Request,
    application_id: int,
    status_value: str = Form(..., alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_recruiter_or_hiring_manager),
):
    app_service = ApplicationService(db)
    audit_service = AuditTrailService(db)

    try:
        application = await app_service.get_application(application_id)
        if application is None:
            return RedirectResponse(
                url="/applications",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        old_status = application.status

        updated_application = await app_service.update_status(
            application_id=application_id,
            new_status=status_value,
            user_id=current_user.id,
        )

        await audit_service.log_action(
            user_id=current_user.id,
            action="update",
            entity_type="Application",
            entity_id=application_id,
            details=f"Status changed from '{old_status}' to '{status_value}'",
        )

        referer = request.headers.get("referer", "")
        if "pipeline" in referer:
            job_id_param = ""
            if "job_id=" in referer:
                try:
                    import urllib.parse

                    parsed = urllib.parse.urlparse(referer)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "job_id" in params and params["job_id"][0]:
                        job_id_param = f"?job_id={params['job_id'][0]}"
                except Exception:
                    pass
            return RedirectResponse(
                url=f"/applications/pipeline{job_id_param}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        return RedirectResponse(
            url=f"/applications/{application_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except ValueError as e:
        logger.warning(
            "Failed to update application %d status: %s (user_id=%d)",
            application_id,
            str(e),
            current_user.id,
        )

        from app.services.interview_service import InterviewService

        interview_service = InterviewService(db)

        application = await app_service.get_application(application_id)
        if application is None:
            return RedirectResponse(
                url="/applications",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        candidate = application.candidate if application.candidate else None
        job = application.job if application.job else None
        interviews = await interview_service.get_interviews_for_application(
            application_id
        )
        allowed_transitions = ALLOWED_TRANSITIONS.get(application.status, [])

        return templates.TemplateResponse(
            request,
            "applications/detail.html",
            context={
                "user": current_user,
                "application": application,
                "candidate": candidate,
                "job": job,
                "interviews": interviews,
                "allowed_transitions": allowed_transitions,
                "messages": [{"type": "error", "text": str(e)}],
            },
            status_code=400,
        )


def _enrich_application(app):
    candidate_name = None
    if app.candidate:
        candidate_name = f"{app.candidate.first_name} {app.candidate.last_name}"

    job_title = None
    if app.job:
        job_title = app.job.title

    class EnrichedApplication:
        pass

    enriched = EnrichedApplication()
    enriched.id = app.id
    enriched.job_id = app.job_id
    enriched.candidate_id = app.candidate_id
    enriched.status = app.status
    enriched.applied_at = app.applied_at
    enriched.updated_at = app.updated_at
    enriched.candidate_name = candidate_name
    enriched.job_title = job_title
    enriched.candidate = app.candidate
    enriched.job = app.job
    enriched.interviews = app.interviews

    return enriched