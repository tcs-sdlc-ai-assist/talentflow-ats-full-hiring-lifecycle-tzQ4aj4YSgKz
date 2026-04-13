import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import (
    get_current_user,
    require_admin,
    require_admin_or_recruiter,
    require_any_role,
)
from app.models.user import User
from app.services.candidate_service import CandidateService
from app.services.application_service import ApplicationService
from app.services.audit_service import AuditTrailService
from app.schemas.candidate import CandidateCreate, CandidateUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

_templates = None


def _get_templates():
    global _templates
    if _templates is None:
        from pathlib import Path
        from fastapi.templating import Jinja2Templates

        templates_dir = str(Path(__file__).resolve().parent.parent / "templates")
        _templates = Jinja2Templates(directory=templates_dir)
    return _templates


@router.get("/candidates")
async def list_candidates(
    request: Request,
    page: int = 1,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    templates = _get_templates()
    page_size = 20

    service = CandidateService(db)
    candidates, total = await service.list_candidates(
        search=search,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return templates.TemplateResponse(
        request,
        "candidates/list.html",
        context={
            "user": current_user,
            "candidates": candidates,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "search": search or "",
        },
    )


@router.get("/candidates/create")
async def create_candidate_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    templates = _get_templates()

    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": current_user,
            "candidate": None,
            "error": None,
        },
    )


@router.post("/candidates/create")
async def create_candidate_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    resume_text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    templates = _get_templates()

    skills_list: Optional[list[str]] = None
    if skills and skills.strip():
        skills_list = [s.strip() for s in skills.split(",") if s.strip()]

    phone_val = phone.strip() if phone and phone.strip() else None
    linkedin_val = linkedin_url.strip() if linkedin_url and linkedin_url.strip() else None
    resume_val = resume_text.strip() if resume_text and resume_text.strip() else None

    try:
        candidate_data = CandidateCreate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone_val,
            linkedin_url=linkedin_val,
            resume_text=resume_val,
            skills=skills_list,
        )
    except Exception as e:
        logger.warning("Candidate creation validation error: %s", e)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": current_user,
                "candidate": None,
                "error": str(e),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        service = CandidateService(db)
        candidate = await service.create_candidate(candidate_data)

        audit_service = AuditTrailService(db)
        await audit_service.log_action(
            user_id=current_user.id,
            action="create",
            entity_type="Candidate",
            entity_id=candidate.id,
            details=f"Created candidate: {candidate.first_name} {candidate.last_name} ({candidate.email})",
        )

        logger.info(
            "Candidate created: id=%d by user_id=%d",
            candidate.id,
            current_user.id,
        )
        return RedirectResponse(
            url=f"/candidates/{candidate.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as e:
        logger.warning("Candidate creation error: %s", e)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": current_user,
                "candidate": None,
                "error": str(e),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@router.get("/candidates/{candidate_id}")
async def candidate_detail(
    request: Request,
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    templates = _get_templates()

    service = CandidateService(db)
    candidate = await service.get_candidate_by_id(candidate_id)

    if candidate is None:
        return templates.TemplateResponse(
            request,
            "candidates/list.html",
            context={
                "user": current_user,
                "candidates": [],
                "total": 0,
                "page": 1,
                "total_pages": 0,
                "search": "",
                "messages": [{"type": "error", "text": f"Candidate with id {candidate_id} not found."}],
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )

    app_service = ApplicationService(db)
    applications = await app_service.get_applications_for_candidate(candidate_id)

    enriched_applications = []
    for app in applications:
        app_dict = app
        if hasattr(app, "job") and app.job:
            app_dict.job_title = app.job.title
        else:
            app_dict.job_title = None
        enriched_applications.append(app_dict)

    return templates.TemplateResponse(
        request,
        "candidates/detail.html",
        context={
            "user": current_user,
            "candidate": candidate,
            "applications": enriched_applications,
        },
    )


@router.get("/candidates/{candidate_id}/edit")
async def edit_candidate_form(
    request: Request,
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    templates = _get_templates()

    service = CandidateService(db)
    candidate = await service.get_candidate_by_id(candidate_id)

    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "candidates/form.html",
        context={
            "user": current_user,
            "candidate": candidate,
            "error": None,
        },
    )


@router.post("/candidates/{candidate_id}/edit")
async def edit_candidate_submit(
    request: Request,
    candidate_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    resume_text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    templates = _get_templates()

    service = CandidateService(db)
    candidate = await service.get_candidate_by_id(candidate_id)

    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=status.HTTP_303_SEE_OTHER)

    skills_list: Optional[list[str]] = None
    if skills is not None:
        if skills.strip():
            skills_list = [s.strip() for s in skills.split(",") if s.strip()]
        else:
            skills_list = []

    phone_val = phone.strip() if phone and phone.strip() else None
    linkedin_val = linkedin_url.strip() if linkedin_url and linkedin_url.strip() else None
    resume_val = resume_text.strip() if resume_text and resume_text.strip() else None

    try:
        update_data = CandidateUpdate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone_val,
            linkedin_url=linkedin_val,
            resume_text=resume_val,
            skills=skills_list,
        )
    except Exception as e:
        logger.warning("Candidate update validation error: %s", e)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": current_user,
                "candidate": candidate,
                "error": str(e),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        updated_candidate = await service.update_candidate(candidate_id, update_data)

        audit_service = AuditTrailService(db)
        await audit_service.log_action(
            user_id=current_user.id,
            action="update",
            entity_type="Candidate",
            entity_id=updated_candidate.id,
            details=f"Updated candidate: {updated_candidate.first_name} {updated_candidate.last_name}",
        )

        logger.info(
            "Candidate updated: id=%d by user_id=%d",
            updated_candidate.id,
            current_user.id,
        )
        return RedirectResponse(
            url=f"/candidates/{updated_candidate.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as e:
        logger.warning("Candidate update error: %s", e)
        return templates.TemplateResponse(
            request,
            "candidates/form.html",
            context={
                "user": current_user,
                "candidate": candidate,
                "error": str(e),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@router.post("/candidates/{candidate_id}/skills")
async def add_candidate_skill(
    request: Request,
    candidate_id: int,
    skill_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    service = CandidateService(db)

    try:
        candidate = await service.add_skill(candidate_id, skill_name)

        audit_service = AuditTrailService(db)
        await audit_service.log_action(
            user_id=current_user.id,
            action="update",
            entity_type="Candidate",
            entity_id=candidate.id,
            details=f"Added skill '{skill_name}' to candidate: {candidate.first_name} {candidate.last_name}",
        )

        logger.info(
            "Skill '%s' added to candidate id=%d by user_id=%d",
            skill_name,
            candidate_id,
            current_user.id,
        )
    except ValueError as e:
        logger.warning("Add skill error for candidate %d: %s", candidate_id, e)

    return RedirectResponse(
        url=f"/candidates/{candidate_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/candidates/{candidate_id}/skills/{skill_id}/remove")
async def remove_candidate_skill(
    request: Request,
    candidate_id: int,
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_recruiter),
):
    service = CandidateService(db)

    try:
        candidate = await service.remove_skill(candidate_id, skill_id)

        audit_service = AuditTrailService(db)
        await audit_service.log_action(
            user_id=current_user.id,
            action="update",
            entity_type="Candidate",
            entity_id=candidate.id,
            details=f"Removed skill id={skill_id} from candidate: {candidate.first_name} {candidate.last_name}",
        )

        logger.info(
            "Skill id=%d removed from candidate id=%d by user_id=%d",
            skill_id,
            candidate_id,
            current_user.id,
        )
    except ValueError as e:
        logger.warning("Remove skill error for candidate %d: %s", candidate_id, e)

    return RedirectResponse(
        url=f"/candidates/{candidate_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )