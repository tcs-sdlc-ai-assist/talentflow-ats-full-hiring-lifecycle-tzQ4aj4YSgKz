import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import COOKIE_NAME, verify_session_cookie
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        return None

    user_id = verify_session_cookie(cookie_value)
    if user_id is None:
        return None

    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    except Exception:
        logger.exception("Error fetching user from session (user_id=%s)", user_id)
        return None

    if user is None:
        logger.warning("Session references non-existent user_id=%s", user_id)
        return None

    if not user.is_active:
        logger.info("Session references inactive user_id=%s", user_id)
        return None

    return user


def require_roles(*allowed_roles: str):
    async def role_checker(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user),
    ) -> User:
        if current_user is None:
            from fastapi.responses import RedirectResponse

            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="Authentication required",
                headers={"Location": "/auth/login"},
            )

        if current_user.role not in allowed_roles:
            logger.warning(
                "User %s (role=%s) denied access to %s %s. Allowed roles: %s",
                current_user.username,
                current_user.role,
                request.method,
                request.url.path,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}",
            )

        return current_user

    return role_checker


require_admin = require_roles("Admin")
require_admin_or_recruiter = require_roles("Admin", "Recruiter")
require_admin_or_hiring_manager = require_roles("Admin", "Hiring Manager")
require_admin_recruiter_or_hiring_manager = require_roles("Admin", "Recruiter", "Hiring Manager")
require_interviewer = require_roles("Interviewer")
require_any_role = require_roles("Admin", "Recruiter", "Hiring Manager", "Interviewer")