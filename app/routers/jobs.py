import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import (
    get_current_user,
    require_admin_or_hiring_manager,
    require_any_role,
)
from app.models.user import User
from app.services.job_service import JobService
from app.services.audit_service import AuditTrailService
from app.schemas.job import JobCreate, JobFilterParams, JobUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/jobs")
async def list_jobs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    department: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Response:
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    job_service = JobService(db)

    filters = JobFilterParams(
        search=search,
        status=status_filter,
        department=department,
        location=location,
        page=page,
        page_size=page_size,
    )

    result = await job_service.list_jobs(filters)

    jobs_with_manager = []
    for job in result["items"]:
        job_data = job
        job_data.hiring_manager_name = (
            job.hiring_manager.full_name if job.hiring_manager else None
        )
        jobs_with_manager.append(job_data)

    return templates.TemplateResponse(
        request,
        "jobs/list.html",
        context={
            "user": current_user,
            "jobs": jobs_with_manager,
            "filters": {
                "search": search or "",
                "status": status_filter or "",
                "department": department or "",
                "location": location or "",
            },
            "pagination": {
                "total": result["total"],
                "page": result["page"],
                "page_size": result["page_size"],
                "total_pages": result["total_pages"],
            },
        },
    )


@router.get("/jobs/create")
async def create_job_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_hiring_manager),
) -> Response:
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(
            User.is_active == True,
            User.role.in_(["Admin", "Hiring Manager"]),
        )
    )
    hiring_managers = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "jobs/form.html",
        context={
            "user": current_user,
            "job": None,
            "hiring_managers": hiring_managers,
            "error": None,
        },
    )


@router.post("/jobs/create")
async def create_job_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_hiring_manager),
    title: str = Form(...),
    description: str = Form(...),
    department: str = Form(""),
    location: str = Form(...),
    salary_range: Optional[str] = Form(None),
    hiring_manager_id: int = Form(...),
) -> Response:
    from sqlalchemy import select

    job_service = JobService(db)
    audit_service = AuditTrailService(db)

    try:
        job_data = JobCreate(
            title=title,
            description=description,
            department=department,
            location=location,
            salary_range=salary_range if salary_range else None,
            hiring_manager_id=hiring_manager_id,
        )
        job = await job_service.create_job(job_data)

        await audit_service.log_action(
            user_id=current_user.id,
            action="create",
            entity_type="Job",
            entity_id=job.id,
            details=f"Created job '{job.title}'",
        )

        logger.info(
            "Job created: id=%d title='%s' by user_id=%d",
            job.id,
            job.title,
            current_user.id,
        )
        return RedirectResponse(
            url=f"/jobs/{job.id}", status_code=status.HTTP_303_SEE_OTHER
        )
    except (ValueError, Exception) as e:
        logger.warning("Failed to create job: %s", str(e))

        result = await db.execute(
            select(User).where(
                User.is_active == True,
                User.role.in_(["Admin", "Hiring Manager"]),
            )
        )
        hiring_managers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": current_user,
                "job": None,
                "hiring_managers": hiring_managers,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/jobs/{job_id}")
async def job_detail(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
) -> Response:
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if job is None:
        return templates.TemplateResponse(
            request,
            "jobs/detail.html",
            context={
                "user": current_user,
                "job": None,
                "hiring_manager": None,
                "applications": [],
                "error": f"Job with id {job_id} not found.",
            },
            status_code=404,
        )

    hiring_manager = job.hiring_manager
    applications = job.applications if job.applications else []

    return templates.TemplateResponse(
        request,
        "jobs/detail.html",
        context={
            "user": current_user,
            "job": job,
            "hiring_manager": hiring_manager,
            "applications": applications,
        },
    )


@router.get("/jobs/{job_id}/edit")
async def edit_job_form(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_hiring_manager),
) -> Response:
    from sqlalchemy import select

    job_service = JobService(db)
    job = await job_service.get_job(job_id)

    if job is None:
        return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)

    if current_user.role == "Hiring Manager" and job.hiring_manager_id != current_user.id:
        return RedirectResponse(
            url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    result = await db.execute(
        select(User).where(
            User.is_active == True,
            User.role.in_(["Admin", "Hiring Manager"]),
        )
    )
    hiring_managers = list(result.scalars().all())

    return templates.TemplateResponse(
        request,
        "jobs/form.html",
        context={
            "user": current_user,
            "job": job,
            "hiring_managers": hiring_managers,
            "error": None,
        },
    )


@router.post("/jobs/{job_id}/edit")
async def edit_job_submit(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_hiring_manager),
    title: str = Form(...),
    description: str = Form(...),
    department: str = Form(""),
    location: str = Form(...),
    salary_range: Optional[str] = Form(None),
    hiring_manager_id: int = Form(...),
    job_status: Optional[str] = Form(None, alias="status"),
) -> Response:
    from sqlalchemy import select

    job_service = JobService(db)
    audit_service = AuditTrailService(db)

    job = await job_service.get_job(job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)

    if current_user.role == "Hiring Manager" and job.hiring_manager_id != current_user.id:
        return RedirectResponse(
            url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    try:
        job_update = JobUpdate(
            title=title,
            description=description,
            department=department,
            location=location,
            salary_range=salary_range if salary_range else None,
            hiring_manager_id=hiring_manager_id,
        )
        updated_job = await job_service.update_job(job_id, job_update)

        if updated_job is None:
            return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)

        if job_status and job_status != updated_job.status:
            try:
                await job_service.change_status(job_id, job_status)
            except ValueError as status_err:
                logger.warning(
                    "Failed to change job %d status to '%s': %s",
                    job_id,
                    job_status,
                    str(status_err),
                )

        await audit_service.log_action(
            user_id=current_user.id,
            action="update",
            entity_type="Job",
            entity_id=job_id,
            details=f"Updated job '{title}'",
        )

        logger.info(
            "Job updated: id=%d by user_id=%d",
            job_id,
            current_user.id,
        )
        return RedirectResponse(
            url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER
        )
    except (ValueError, Exception) as e:
        logger.warning("Failed to update job %d: %s", job_id, str(e))

        result = await db.execute(
            select(User).where(
                User.is_active == True,
                User.role.in_(["Admin", "Hiring Manager"]),
            )
        )
        hiring_managers = list(result.scalars().all())

        return templates.TemplateResponse(
            request,
            "jobs/form.html",
            context={
                "user": current_user,
                "job": job,
                "hiring_managers": hiring_managers,
                "error": str(e),
            },
            status_code=400,
        )


@router.post("/jobs/{job_id}/status")
async def change_job_status(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_hiring_manager),
    new_status: str = Form(..., alias="status"),
) -> Response:
    job_service = JobService(db)
    audit_service = AuditTrailService(db)

    job = await job_service.get_job(job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)

    if current_user.role == "Hiring Manager" and job.hiring_manager_id != current_user.id:
        return RedirectResponse(
            url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    old_status = job.status

    try:
        updated_job = await job_service.change_status(job_id, new_status)

        if updated_job is not None:
            await audit_service.log_action(
                user_id=current_user.id,
                action="update",
                entity_type="Job",
                entity_id=job_id,
                details=f"Changed job status from '{old_status}' to '{new_status}'",
            )

            logger.info(
                "Job %d status changed: '%s' -> '%s' by user_id=%d",
                job_id,
                old_status,
                new_status,
                current_user.id,
            )

        return RedirectResponse(
            url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER
        )
    except ValueError as e:
        logger.warning(
            "Failed to change job %d status to '%s': %s",
            job_id,
            new_status,
            str(e),
        )
        return RedirectResponse(
            url=f"/jobs/{job_id}", status_code=status.HTTP_303_SEE_OTHER
        )