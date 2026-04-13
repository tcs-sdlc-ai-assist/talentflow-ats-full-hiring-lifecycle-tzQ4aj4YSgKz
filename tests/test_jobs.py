import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import User
from app.core.security import get_password_hash, create_session_cookie, COOKIE_NAME


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Senior Backend Engineer",
        description="Design and build scalable APIs using Python and FastAPI.",
        department="Engineering",
        location="Remote",
        salary_range="120000-150000",
        status="Draft",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    await db_session.commit()
    return job


@pytest_asyncio.fixture
async def open_job(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Frontend Developer",
        description="Build beautiful UIs with React and TypeScript.",
        department="Engineering",
        location="New York, NY",
        salary_range="100000-130000",
        status="Open",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    await db_session.commit()
    return job


@pytest_asyncio.fixture
async def hiring_manager_job(db_session: AsyncSession, hiring_manager_user: User) -> Job:
    job = Job(
        title="Product Manager",
        description="Lead product strategy and roadmap.",
        department="Product",
        location="San Francisco, CA",
        salary_range="130000-160000",
        status="Open",
        hiring_manager_id=hiring_manager_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    await db_session.commit()
    return job


# ============================================================
# Job Listing Tests
# ============================================================


class TestListJobs:
    async def test_list_jobs_authenticated_returns_200(
        self, admin_client: AsyncClient, sample_job: Job
    ):
        response = await admin_client.get("/jobs")
        assert response.status_code == 200
        assert "Senior Backend Engineer" in response.text

    async def test_list_jobs_unauthenticated_redirects_to_login(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get("/jobs", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_list_jobs_with_status_filter(
        self, admin_client: AsyncClient, sample_job: Job, open_job: Job
    ):
        response = await admin_client.get("/jobs?status=Open")
        assert response.status_code == 200
        assert "Frontend Developer" in response.text

    async def test_list_jobs_with_search_filter(
        self, admin_client: AsyncClient, sample_job: Job, open_job: Job
    ):
        response = await admin_client.get("/jobs?search=Backend")
        assert response.status_code == 200
        assert "Senior Backend Engineer" in response.text

    async def test_list_jobs_with_department_filter(
        self, admin_client: AsyncClient, sample_job: Job, hiring_manager_job: Job
    ):
        response = await admin_client.get("/jobs?department=Product")
        assert response.status_code == 200
        assert "Product Manager" in response.text

    async def test_list_jobs_empty_result(self, admin_client: AsyncClient):
        response = await admin_client.get("/jobs?status=Cancelled")
        assert response.status_code == 200
        assert "No jobs found" in response.text

    async def test_list_jobs_all_roles_can_view(
        self,
        recruiter_client: AsyncClient,
        interviewer_client: AsyncClient,
        hiring_manager_client: AsyncClient,
        sample_job: Job,
    ):
        for client in [recruiter_client, interviewer_client, hiring_manager_client]:
            response = await client.get("/jobs")
            assert response.status_code == 200


# ============================================================
# Job Detail Tests
# ============================================================


class TestJobDetail:
    async def test_get_job_detail_returns_200(
        self, admin_client: AsyncClient, sample_job: Job
    ):
        response = await admin_client.get(f"/jobs/{sample_job.id}")
        assert response.status_code == 200
        assert "Senior Backend Engineer" in response.text
        assert "Engineering" in response.text
        assert "Remote" in response.text

    async def test_get_job_detail_not_found_returns_404(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/jobs/99999")
        assert response.status_code == 404

    async def test_get_job_detail_unauthenticated_redirects(
        self, unauthenticated_client: AsyncClient, sample_job: Job
    ):
        response = await unauthenticated_client.get(
            f"/jobs/{sample_job.id}", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_get_job_detail_shows_hiring_manager(
        self, admin_client: AsyncClient, sample_job: Job, admin_user: User
    ):
        response = await admin_client.get(f"/jobs/{sample_job.id}")
        assert response.status_code == 200
        assert admin_user.full_name in response.text


# ============================================================
# Job Creation Tests
# ============================================================


class TestCreateJob:
    async def test_create_job_form_admin_returns_200(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/jobs/create")
        assert response.status_code == 200
        assert "Create" in response.text

    async def test_create_job_form_hiring_manager_returns_200(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get("/jobs/create")
        assert response.status_code == 200

    async def test_create_job_form_recruiter_forbidden(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get("/jobs/create")
        assert response.status_code == 403

    async def test_create_job_form_interviewer_forbidden(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get("/jobs/create")
        assert response.status_code == 403

    async def test_create_job_submit_admin_success(
        self, admin_client: AsyncClient, admin_user: User, db_session: AsyncSession
    ):
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Data Scientist",
                "description": "Analyze data and build ML models.",
                "department": "Data",
                "location": "Boston, MA",
                "salary_range": "110000-140000",
                "hiring_manager_id": str(admin_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/jobs/" in location

        result = await db_session.execute(
            select(Job).where(Job.title == "Data Scientist")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"
        assert job.department == "Data"
        assert job.location == "Boston, MA"

    async def test_create_job_submit_hiring_manager_success(
        self,
        hiring_manager_client: AsyncClient,
        hiring_manager_user: User,
        db_session: AsyncSession,
    ):
        response = await hiring_manager_client.post(
            "/jobs/create",
            data={
                "title": "QA Engineer",
                "description": "Ensure quality of software products.",
                "department": "QA",
                "location": "Remote",
                "salary_range": "90000-120000",
                "hiring_manager_id": str(hiring_manager_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_create_job_submit_recruiter_forbidden(
        self, recruiter_client: AsyncClient, admin_user: User
    ):
        response = await recruiter_client.post(
            "/jobs/create",
            data={
                "title": "Test Job",
                "description": "Should not be created.",
                "department": "Test",
                "location": "Nowhere",
                "hiring_manager_id": str(admin_user.id),
            },
        )
        assert response.status_code == 403

    async def test_create_job_submit_interviewer_forbidden(
        self, interviewer_client: AsyncClient, admin_user: User
    ):
        response = await interviewer_client.post(
            "/jobs/create",
            data={
                "title": "Test Job",
                "description": "Should not be created.",
                "department": "Test",
                "location": "Nowhere",
                "hiring_manager_id": str(admin_user.id),
            },
        )
        assert response.status_code == 403

    async def test_create_job_defaults_to_draft_status(
        self, admin_client: AsyncClient, admin_user: User, db_session: AsyncSession
    ):
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "DevOps Engineer",
                "description": "Manage CI/CD pipelines and infrastructure.",
                "department": "Infrastructure",
                "location": "Remote",
                "hiring_manager_id": str(admin_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        result = await db_session.execute(
            select(Job).where(Job.title == "DevOps Engineer")
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"

    async def test_create_job_invalid_hiring_manager_returns_error(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Ghost Job",
                "description": "This should fail.",
                "department": "None",
                "location": "Nowhere",
                "hiring_manager_id": "99999",
            },
        )
        assert response.status_code == 400

    async def test_create_job_unauthenticated_redirects(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.post(
            "/jobs/create",
            data={
                "title": "Test",
                "description": "Test",
                "department": "Test",
                "location": "Test",
                "hiring_manager_id": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code in (303, 401, 403)


# ============================================================
# Job Edit Tests
# ============================================================


class TestEditJob:
    async def test_edit_job_form_admin_returns_200(
        self, admin_client: AsyncClient, sample_job: Job
    ):
        response = await admin_client.get(f"/jobs/{sample_job.id}/edit")
        assert response.status_code == 200
        assert sample_job.title in response.text

    async def test_edit_job_form_hiring_manager_own_job(
        self, hiring_manager_client: AsyncClient, hiring_manager_job: Job
    ):
        response = await hiring_manager_client.get(
            f"/jobs/{hiring_manager_job.id}/edit"
        )
        assert response.status_code == 200
        assert hiring_manager_job.title in response.text

    async def test_edit_job_form_hiring_manager_other_job_redirects(
        self, hiring_manager_client: AsyncClient, sample_job: Job
    ):
        response = await hiring_manager_client.get(
            f"/jobs/{sample_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 303

    async def test_edit_job_submit_admin_success(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        admin_user: User,
        db_session: AsyncSession,
    ):
        response = await admin_client.post(
            f"/jobs/{sample_job.id}/edit",
            data={
                "title": "Updated Title",
                "description": "Updated description for the role.",
                "department": "Updated Dept",
                "location": "Updated Location",
                "salary_range": "150000-180000",
                "hiring_manager_id": str(admin_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        updated_job = result.scalar_one_or_none()
        assert updated_job is not None
        assert updated_job.title == "Updated Title"
        assert updated_job.department == "Updated Dept"

    async def test_edit_job_not_found_redirects(self, admin_client: AsyncClient):
        response = await admin_client.get("/jobs/99999/edit", follow_redirects=False)
        assert response.status_code == 303

    async def test_edit_job_recruiter_forbidden(
        self, recruiter_client: AsyncClient, sample_job: Job
    ):
        response = await recruiter_client.get(f"/jobs/{sample_job.id}/edit")
        assert response.status_code == 403


# ============================================================
# Job Status Transition Tests
# ============================================================


class TestJobStatusTransitions:
    async def test_draft_to_open_success(
        self, admin_client: AsyncClient, sample_job: Job, db_session: AsyncSession
    ):
        assert sample_job.status == "Draft"
        response = await admin_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Open"

    async def test_draft_to_cancelled_success(
        self, admin_client: AsyncClient, sample_job: Job, db_session: AsyncSession
    ):
        response = await admin_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Cancelled"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Cancelled"

    async def test_open_to_closed_success(
        self, admin_client: AsyncClient, open_job: Job, db_session: AsyncSession
    ):
        response = await admin_client.post(
            f"/jobs/{open_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == open_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Closed"

    async def test_open_to_on_hold_success(
        self, admin_client: AsyncClient, open_job: Job, db_session: AsyncSession
    ):
        response = await admin_client.post(
            f"/jobs/{open_job.id}/status",
            data={"status": "On Hold"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == open_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "On Hold"

    async def test_invalid_transition_draft_to_closed_redirects(
        self, admin_client: AsyncClient, sample_job: Job, db_session: AsyncSession
    ):
        assert sample_job.status == "Draft"
        response = await admin_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"

    async def test_invalid_transition_draft_to_on_hold_stays_draft(
        self, admin_client: AsyncClient, sample_job: Job, db_session: AsyncSession
    ):
        response = await admin_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "On Hold"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"

    async def test_status_change_recruiter_forbidden(
        self, recruiter_client: AsyncClient, sample_job: Job
    ):
        response = await recruiter_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Open"},
        )
        assert response.status_code == 403

    async def test_status_change_interviewer_forbidden(
        self, interviewer_client: AsyncClient, sample_job: Job
    ):
        response = await interviewer_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Open"},
        )
        assert response.status_code == 403

    async def test_hiring_manager_can_change_own_job_status(
        self,
        hiring_manager_client: AsyncClient,
        hiring_manager_job: Job,
        db_session: AsyncSession,
    ):
        response = await hiring_manager_client.post(
            f"/jobs/{hiring_manager_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == hiring_manager_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Closed"

    async def test_hiring_manager_cannot_change_other_job_status(
        self,
        hiring_manager_client: AsyncClient,
        sample_job: Job,
        db_session: AsyncSession,
    ):
        response = await hiring_manager_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"

    async def test_status_change_nonexistent_job_redirects(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.post(
            "/jobs/99999/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_closed_to_open_success(
        self, admin_client: AsyncClient, open_job: Job, db_session: AsyncSession
    ):
        await admin_client.post(
            f"/jobs/{open_job.id}/status",
            data={"status": "Closed"},
            follow_redirects=False,
        )

        response = await admin_client.post(
            f"/jobs/{open_job.id}/status",
            data={"status": "Open"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == open_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Open"

    async def test_cancelled_to_draft_success(
        self, admin_client: AsyncClient, sample_job: Job, db_session: AsyncSession
    ):
        await admin_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Cancelled"},
            follow_redirects=False,
        )

        response = await admin_client.post(
            f"/jobs/{sample_job.id}/status",
            data={"status": "Draft"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == sample_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.status == "Draft"


# ============================================================
# Landing Page / Public Job Listings Tests
# ============================================================


class TestPublicJobListings:
    async def test_landing_page_shows_open_jobs(
        self, unauthenticated_client: AsyncClient, open_job: Job
    ):
        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Frontend Developer" in response.text

    async def test_landing_page_does_not_show_draft_jobs(
        self, unauthenticated_client: AsyncClient, sample_job: Job
    ):
        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Senior Backend Engineer" not in response.text

    async def test_landing_page_shows_multiple_open_jobs(
        self,
        unauthenticated_client: AsyncClient,
        open_job: Job,
        hiring_manager_job: Job,
    ):
        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "Frontend Developer" in response.text
        assert "Product Manager" in response.text

    async def test_landing_page_authenticated_shows_dashboard_link(
        self, admin_client: AsyncClient, open_job: Job
    ):
        response = await admin_client.get("/")
        assert response.status_code == 200
        assert "Dashboard" in response.text or "dashboard" in response.text.lower()

    async def test_landing_page_no_open_jobs_shows_empty_state(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get("/")
        assert response.status_code == 200
        assert "No Open Positions" in response.text or "no open positions" in response.text.lower()


# ============================================================
# Hiring Manager Own Jobs Tests
# ============================================================


class TestHiringManagerOwnJobs:
    async def test_hiring_manager_sees_own_job_in_list(
        self, hiring_manager_client: AsyncClient, hiring_manager_job: Job
    ):
        response = await hiring_manager_client.get("/jobs")
        assert response.status_code == 200
        assert "Product Manager" in response.text

    async def test_hiring_manager_can_view_own_job_detail(
        self, hiring_manager_client: AsyncClient, hiring_manager_job: Job
    ):
        response = await hiring_manager_client.get(
            f"/jobs/{hiring_manager_job.id}"
        )
        assert response.status_code == 200
        assert "Product Manager" in response.text

    async def test_hiring_manager_can_edit_own_job(
        self,
        hiring_manager_client: AsyncClient,
        hiring_manager_job: Job,
        hiring_manager_user: User,
        db_session: AsyncSession,
    ):
        response = await hiring_manager_client.post(
            f"/jobs/{hiring_manager_job.id}/edit",
            data={
                "title": "Senior Product Manager",
                "description": "Lead product strategy and roadmap at scale.",
                "department": "Product",
                "location": "San Francisco, CA",
                "salary_range": "150000-180000",
                "hiring_manager_id": str(hiring_manager_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        await db_session.expire_all()
        result = await db_session.execute(
            select(Job).where(Job.id == hiring_manager_job.id)
        )
        job = result.scalar_one_or_none()
        assert job is not None
        assert job.title == "Senior Product Manager"

    async def test_hiring_manager_cannot_edit_other_managers_job(
        self,
        hiring_manager_client: AsyncClient,
        sample_job: Job,
    ):
        response = await hiring_manager_client.get(
            f"/jobs/{sample_job.id}/edit", follow_redirects=False
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert f"/jobs/{sample_job.id}" in location

    async def test_hiring_manager_can_also_see_other_jobs_in_list(
        self,
        hiring_manager_client: AsyncClient,
        sample_job: Job,
        hiring_manager_job: Job,
    ):
        response = await hiring_manager_client.get("/jobs")
        assert response.status_code == 200
        assert "Senior Backend Engineer" in response.text
        assert "Product Manager" in response.text


# ============================================================
# Job Service Unit Tests
# ============================================================


class TestJobService:
    async def test_create_job_via_service(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate

        service = JobService(db_session)
        job_data = JobCreate(
            title="ML Engineer",
            description="Build and deploy machine learning models.",
            department="AI",
            location="Remote",
            salary_range="140000-170000",
            hiring_manager_id=admin_user.id,
        )
        job = await service.create_job(job_data)
        assert job.id is not None
        assert job.title == "ML Engineer"
        assert job.status == "Draft"

    async def test_create_job_invalid_manager_raises(
        self, db_session: AsyncSession
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate

        service = JobService(db_session)
        job_data = JobCreate(
            title="Ghost Job",
            description="Should fail.",
            department="None",
            location="Nowhere",
            hiring_manager_id=99999,
        )
        with pytest.raises(ValueError, match="not found"):
            await service.create_job(job_data)

    async def test_change_status_valid_transition(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate

        service = JobService(db_session)
        job_data = JobCreate(
            title="Test Status Job",
            description="Testing status transitions.",
            department="Test",
            location="Test",
            hiring_manager_id=admin_user.id,
        )
        job = await service.create_job(job_data)
        assert job.status == "Draft"

        updated = await service.change_status(job.id, "Open")
        assert updated is not None
        assert updated.status == "Open"

    async def test_change_status_invalid_transition_raises(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate

        service = JobService(db_session)
        job_data = JobCreate(
            title="Test Invalid Transition",
            description="Testing invalid status transitions.",
            department="Test",
            location="Test",
            hiring_manager_id=admin_user.id,
        )
        job = await service.create_job(job_data)
        assert job.status == "Draft"

        with pytest.raises(ValueError, match="Invalid status transition"):
            await service.change_status(job.id, "Closed")

    async def test_change_status_invalid_status_value_raises(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate

        service = JobService(db_session)
        job_data = JobCreate(
            title="Test Bad Status",
            description="Testing bad status value.",
            department="Test",
            location="Test",
            hiring_manager_id=admin_user.id,
        )
        job = await service.create_job(job_data)

        with pytest.raises(ValueError, match="Invalid status"):
            await service.change_status(job.id, "Nonexistent")

    async def test_change_status_nonexistent_job_returns_none(
        self, db_session: AsyncSession
    ):
        from app.services.job_service import JobService

        service = JobService(db_session)
        result = await service.change_status(99999, "Open")
        assert result is None

    async def test_update_job_via_service(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate, JobUpdate

        service = JobService(db_session)
        job_data = JobCreate(
            title="Original Title",
            description="Original description.",
            department="Original",
            location="Original",
            hiring_manager_id=admin_user.id,
        )
        job = await service.create_job(job_data)

        update_data = JobUpdate(
            title="New Title",
            description="New description.",
        )
        updated = await service.update_job(job.id, update_data)
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.description == "New description."
        assert updated.department == "Original"

    async def test_get_job_returns_none_for_nonexistent(
        self, db_session: AsyncSession
    ):
        from app.services.job_service import JobService

        service = JobService(db_session)
        result = await service.get_job(99999)
        assert result is None

    async def test_list_published_jobs_only_open(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate

        service = JobService(db_session)

        draft_data = JobCreate(
            title="Draft Job",
            description="This is a draft.",
            department="Test",
            location="Test",
            hiring_manager_id=admin_user.id,
        )
        await service.create_job(draft_data)

        open_data = JobCreate(
            title="Open Job For Public",
            description="This is open.",
            department="Test",
            location="Test",
            hiring_manager_id=admin_user.id,
        )
        open_job = await service.create_job(open_data)
        await service.change_status(open_job.id, "Open")

        published = await service.list_published_jobs()
        titles = [j.title for j in published]
        assert "Open Job For Public" in titles
        assert "Draft Job" not in titles

    async def test_list_jobs_pagination(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate, JobFilterParams

        service = JobService(db_session)

        for i in range(5):
            job_data = JobCreate(
                title=f"Paginated Job {i}",
                description=f"Description for job {i}.",
                department="Test",
                location="Test",
                hiring_manager_id=admin_user.id,
            )
            await service.create_job(job_data)

        filters = JobFilterParams(page=1, page_size=2)
        result = await service.list_jobs(filters)
        assert len(result["items"]) == 2
        assert result["total"] >= 5
        assert result["page"] == 1
        assert result["total_pages"] >= 3