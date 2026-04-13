import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user, require_any_role, require_admin
from app.models.user import User
from app.services.audit_service import AuditTrailService
from app.services.dashboard_service import DashboardService
from app.schemas.audit_log import AuditLogFilterParams

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    dashboard_service = DashboardService(db)
    context_data = await dashboard_service.get_dashboard_context(current_user)

    template_context = {
        "user": current_user,
        "current_year": datetime.utcnow().year,
    }

    metrics = context_data.get("metrics", {})
    template_context["metrics"] = metrics

    if current_user.role in ["Admin", "Recruiter"]:
        template_context["recent_audit_logs"] = context_data.get("recent_audit_logs", [])
    elif current_user.role == "Hiring Manager":
        template_context["my_jobs"] = context_data.get("my_jobs", [])
    elif current_user.role == "Interviewer":
        template_context["my_interviews"] = context_data.get("my_interviews", [])

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        context=template_context,
    )


@router.get("/dashboard/audit-log")
async def audit_log_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    user_id: Optional[int] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    parsed_date_from: Optional[datetime] = None
    parsed_date_to: Optional[datetime] = None

    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from)
        except (ValueError, TypeError):
            logger.warning("Invalid date_from parameter: %s", date_from)

    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to)
        except (ValueError, TypeError):
            logger.warning("Invalid date_to parameter: %s", date_to)

    clean_entity_type = entity_type.strip() if entity_type and entity_type.strip() else None
    clean_action = action.strip() if action and action.strip() else None

    filters = AuditLogFilterParams(
        page=page,
        per_page=per_page,
        user_id=user_id,
        entity_type=clean_entity_type,
        entity_id=entity_id,
        action=clean_action,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )

    audit_service = AuditTrailService(db)
    audit_log_response = await audit_service.query_logs(filters=filters)

    template_context = {
        "user": current_user,
        "current_year": datetime.utcnow().year,
        "audit_logs": audit_log_response.items,
        "total": audit_log_response.total,
        "page": audit_log_response.page,
        "per_page": audit_log_response.per_page,
        "total_pages": audit_log_response.total_pages,
        "filters": {
            "user_id": user_id,
            "entity_type": clean_entity_type or "",
            "entity_id": entity_id,
            "action": clean_action or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
    }

    return templates.TemplateResponse(
        request,
        "dashboard/audit_log.html",
        context=template_context,
    )


@router.get("/dashboard/metrics")
async def dashboard_metrics(
    request: Request,
    current_user: User = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    dashboard_service = DashboardService(db)
    metrics = await dashboard_service.get_metrics(current_user)
    return metrics