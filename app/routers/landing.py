import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/")
async def landing_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
) -> Response:
    job_service = JobService(db)
    jobs = await job_service.list_published_jobs()

    return templates.TemplateResponse(
        request,
        "landing.html",
        context={
            "user": user,
            "jobs": jobs,
        },
    )