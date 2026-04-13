import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import COOKIE_NAME, SESSION_MAX_AGE, create_session_cookie
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/login")
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        context={"error": None, "username": ""},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)

    username = username.strip()

    if not username or not password:
        logger.info("Login attempt with empty username or password")
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "error": "Username and password are required.",
                "username": username,
            },
            status_code=400,
        )

    user = await auth_service.login(username, password)

    if user is None:
        logger.info("Failed login attempt for username='%s'", username)
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=401,
        )

    session_cookie = create_session_cookie(user.id)

    redirect_url = _get_redirect_url_for_role(user.role)
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_cookie,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )

    logger.info(
        "User '%s' (id=%d, role=%s) logged in successfully, redirecting to %s",
        user.username,
        user.id,
        user.role,
        redirect_url,
    )
    return response


@router.get("/register")
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "auth/register.html",
        context={
            "error": None,
            "username": "",
            "full_name": "",
        },
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)

    username = username.strip()
    full_name = full_name.strip()

    if not username or not password or not full_name:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "All fields are required.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if len(username) < 3 or len(username) > 32:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Username must be between 3 and 32 characters.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if not all(c.isalnum() or c == "_" for c in username):
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Username must contain only alphanumeric characters and underscores.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Password must be at least 8 characters.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if " " in password:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Password must not contain spaces.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Passwords do not match.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if len(full_name) < 3 or len(full_name) > 64:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Full name must be between 3 and 64 characters.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    if not all(c.isalpha() or c == " " for c in full_name):
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Full name must contain only letters and spaces.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    user = await auth_service.register(
        username=username,
        password=password,
        full_name=full_name,
        role="Interviewer",
    )

    if user is None:
        logger.warning("Registration failed: username '%s' already exists", username)
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            context={
                "error": "Username already exists. Please choose a different username.",
                "username": username,
                "full_name": full_name,
            },
            status_code=400,
        )

    session_cookie = create_session_cookie(user.id)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_cookie,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )

    logger.info(
        "User '%s' (id=%d, role=%s) registered successfully",
        user.username,
        user.id,
        user.role,
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )

    logger.info("User logged out")
    return response


def _get_redirect_url_for_role(role: str) -> str:
    role_redirects = {
        "Admin": "/dashboard",
        "Recruiter": "/dashboard",
        "Hiring Manager": "/dashboard",
        "Interviewer": "/dashboard",
    }
    return role_redirects.get(role, "/dashboard")