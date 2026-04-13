import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import COOKIE_NAME, create_session_cookie, get_password_hash
from app.models.user import User


class TestLoginFlow:
    """Tests for POST /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_page_renders(self, client: AsyncClient):
        response = await client.get("/auth/login")
        assert response.status_code == 200
        assert "Sign in" in response.text

    @pytest.mark.asyncio
    async def test_login_valid_credentials_redirects_to_dashboard(
        self, client: AsyncClient, admin_user: User
    ):
        response = await client.post(
            "/auth/login",
            data={"username": "testadmin", "password": "adminpass123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"
        assert COOKIE_NAME in response.cookies

    @pytest.mark.asyncio
    async def test_login_invalid_password_returns_401(
        self, client: AsyncClient, admin_user: User
    ):
        response = await client.post(
            "/auth/login",
            data={"username": "testadmin", "password": "wrongpassword"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/auth/login",
            data={"username": "nonexistent", "password": "somepassword"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_empty_username_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/auth/login",
            data={"username": "", "password": "somepassword"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "required" in response.text.lower()

    @pytest.mark.asyncio
    async def test_login_empty_password_returns_400(
        self, client: AsyncClient, admin_user: User
    ):
        response = await client.post(
            "/auth/login",
            data={"username": "testadmin", "password": ""},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "required" in response.text.lower()

    @pytest.mark.asyncio
    async def test_login_inactive_user_returns_401(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        inactive_user = User(
            username="inactiveuser",
            password_hash=get_password_hash("password123"),
            full_name="Inactive User",
            role="Interviewer",
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/login",
            data={"username": "inactiveuser", "password": "password123"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_sets_session_cookie_with_httponly(
        self, client: AsyncClient, admin_user: User
    ):
        response = await client.post(
            "/auth/login",
            data={"username": "testadmin", "password": "adminpass123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "httponly" in set_cookie_header.lower()

    @pytest.mark.asyncio
    async def test_login_redirects_authenticated_user_to_dashboard(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/auth/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"


class TestRegistrationFlow:
    """Tests for POST /auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_page_renders(self, client: AsyncClient):
        response = await client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    @pytest.mark.asyncio
    async def test_register_valid_data_creates_interviewer(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "newinterviewer",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "New Interviewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"
        assert COOKIE_NAME in response.cookies

    @pytest.mark.asyncio
    async def test_register_duplicate_username_returns_400(
        self, client: AsyncClient, admin_user: User
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "testadmin",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "Another Admin",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already exists" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_password_mismatch_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "mismatchuser",
                "password": "securepass123",
                "confirm_password": "differentpass",
                "full_name": "Mismatch User",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "do not match" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_short_password_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "shortpwduser",
                "password": "short",
                "confirm_password": "short",
                "full_name": "Short Password",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "8 characters" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_password_with_spaces_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "spacepwduser",
                "password": "pass word 123",
                "confirm_password": "pass word 123",
                "full_name": "Space Password",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "spaces" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_short_username_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "ab",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "Short Username",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "3 and 32" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_invalid_username_chars_returns_400(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "bad@user!",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "Bad Username",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "alphanumeric" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_empty_full_name_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            data={
                "username": "emptyname",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_register_full_name_with_numbers_returns_400(
        self, client: AsyncClient
    ):
        response = await client.post(
            "/auth/register",
            data={
                "username": "numname",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "Name With 123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "letters and spaces" in response.text.lower()

    @pytest.mark.asyncio
    async def test_register_redirects_authenticated_user_to_dashboard(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/auth/register", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"


class TestLogoutFlow:
    """Tests for POST /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_clears_session_cookie(self, admin_client: AsyncClient):
        response = await admin_client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        set_cookie_header = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie_header

    @pytest.mark.asyncio
    async def test_logout_redirects_to_landing(self, admin_client: AsyncClient):
        response = await admin_client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"


class TestProtectedRouteRedirects:
    """Tests that unauthenticated users are redirected to login."""

    @pytest.mark.asyncio
    async def test_dashboard_redirects_unauthenticated(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/dashboard", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_jobs_redirects_unauthenticated(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_candidates_redirects_unauthenticated(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/candidates", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_applications_redirects_unauthenticated(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_interviews_redirects_unauthenticated(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/interviews", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_landing_page_accessible_without_auth(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get("/", follow_redirects=False)
        assert response.status_code == 200


class TestRBACEnforcement:
    """Tests that role-based access control is enforced correctly."""

    @pytest.mark.asyncio
    async def test_admin_can_access_audit_log(self, admin_client: AsyncClient):
        response = await admin_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_cannot_access_audit_log(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_audit_log(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_hiring_manager_cannot_access_audit_log(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_job_create(self, admin_client: AsyncClient):
        response = await admin_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hiring_manager_can_access_job_create(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/jobs/create", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_cannot_access_job_create(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_job_create(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get("/jobs/create", follow_redirects=False)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_candidate_create(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/candidates/create", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_candidate_create(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_candidate_create(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_hiring_manager_cannot_access_candidate_create(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_application_create(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_application_create(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_application_create(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_all_roles_can_access_dashboard(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_all_roles_can_access_jobs_list(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_all_roles_can_access_candidates_list(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_all_roles_can_access_applications_list(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_all_roles_can_access_interviews_list(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/interviews", follow_redirects=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_interview_schedule(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recruiter_can_access_interview_schedule(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hiring_manager_can_access_interview_schedule(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_interviewer_cannot_access_interview_schedule(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code == 403


class TestSessionManagement:
    """Tests for session cookie validation and expiry."""

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_treated_as_unauthenticated(
        self, client: AsyncClient
    ):
        client.cookies.set(COOKIE_NAME, "invalid-cookie-value")
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]
        client.cookies.clear()

    @pytest.mark.asyncio
    async def test_session_cookie_for_nonexistent_user_treated_as_unauthenticated(
        self, client: AsyncClient
    ):
        cookie_value = create_session_cookie(999999)
        client.cookies.set(COOKIE_NAME, cookie_value)
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]
        client.cookies.clear()

    @pytest.mark.asyncio
    async def test_session_cookie_for_inactive_user_treated_as_unauthenticated(
        self, db_session: AsyncSession, client: AsyncClient
    ):
        inactive_user = User(
            username="inactivesession",
            password_hash=get_password_hash("password123"),
            full_name="Inactive Session",
            role="Interviewer",
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.flush()
        await db_session.refresh(inactive_user)
        await db_session.commit()

        cookie_value = create_session_cookie(inactive_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers["location"]
        client.cookies.clear()

    @pytest.mark.asyncio
    async def test_valid_session_allows_dashboard_access(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200


class TestAuthServiceSeedAdmin:
    """Tests for default admin seeding on startup."""

    @pytest.mark.asyncio
    async def test_default_admin_can_login(self, db_session: AsyncSession, client: AsyncClient):
        from app.services.auth_service import AuthService

        auth_service = AuthService(db_session)
        await auth_service.seed_default_admin()
        await db_session.commit()

        from app.core.config import settings

        response = await client.post(
            "/auth/login",
            data={
                "username": settings.DEFAULT_ADMIN_USERNAME,
                "password": settings.DEFAULT_ADMIN_PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    @pytest.mark.asyncio
    async def test_seed_admin_is_idempotent(self, db_session: AsyncSession):
        from app.services.auth_service import AuthService
        from sqlalchemy import select, func

        auth_service = AuthService(db_session)
        await auth_service.seed_default_admin()
        await db_session.commit()

        await auth_service.seed_default_admin()
        await db_session.commit()

        from app.core.config import settings

        result = await db_session.execute(
            select(func.count()).select_from(User).where(
                User.username == settings.DEFAULT_ADMIN_USERNAME
            )
        )
        count = result.scalar()
        assert count == 1