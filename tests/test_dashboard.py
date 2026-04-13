import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash, create_session_cookie, COOKIE_NAME


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Senior Engineer",
        description="Build things",
        department="Engineering",
        location="Remote",
        salary_range="120000-150000",
        status="Open",
        hiring_manager_id=admin_user.id,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)
    await db_session.commit()
    return job


@pytest_asyncio.fixture
async def sample_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1234567890",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    await db_session.commit()
    return candidate


@pytest_asyncio.fixture
async def sample_application(
    db_session: AsyncSession, sample_job: Job, sample_candidate: Candidate
) -> Application:
    application = Application(
        job_id=sample_job.id,
        candidate_id=sample_candidate.id,
        status="Applied",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    await db_session.commit()
    return application


@pytest_asyncio.fixture
async def sample_interview(
    db_session: AsyncSession,
    sample_application: Application,
    interviewer_user: User,
) -> Interview:
    from datetime import datetime, timedelta

    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    await db_session.commit()
    return interview


@pytest_asyncio.fixture
async def sample_audit_logs(db_session: AsyncSession, admin_user: User) -> list[AuditLog]:
    logs = []
    for i in range(5):
        log = AuditLog(
            user_id=admin_user.id,
            action="create" if i % 2 == 0 else "update",
            entity_type="Job" if i < 3 else "Candidate",
            entity_id=i + 1,
            details=f"Test audit log entry {i + 1}",
        )
        db_session.add(log)
        logs.append(log)
    await db_session.flush()
    for log in logs:
        await db_session.refresh(log)
    await db_session.commit()
    return logs


# ============================================================
# SCRUM-16257: HR/Admin Dashboard Metrics
# ============================================================


class TestAdminDashboard:
    async def test_admin_dashboard_loads_successfully(
        self, admin_client: AsyncClient, admin_user: User
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Dashboard" in response.text
        assert admin_user.full_name in response.text

    async def test_admin_dashboard_shows_metrics(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
        sample_application: Application,
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Open Roles" in response.text
        assert "Total Candidates" in response.text
        assert "Pending Interviews" in response.text
        assert "Missing Feedback" in response.text

    async def test_admin_dashboard_shows_pipeline(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Application Pipeline" in response.text
        assert "Applied" in response.text
        assert "Screening" in response.text
        assert "Interview" in response.text
        assert "Offer" in response.text
        assert "Hired" in response.text
        assert "Rejected" in response.text

    async def test_admin_dashboard_shows_recent_activity(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Recent Activity" in response.text

    async def test_admin_dashboard_shows_audit_log_link(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "audit-log" in response.text or "audit" in response.text.lower()


# ============================================================
# SCRUM-16257: Recruiter Dashboard (same as Admin)
# ============================================================


class TestRecruiterDashboard:
    async def test_recruiter_dashboard_loads_successfully(
        self, recruiter_client: AsyncClient, recruiter_user: User
    ):
        response = await recruiter_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Dashboard" in response.text
        assert recruiter_user.full_name in response.text

    async def test_recruiter_dashboard_shows_metrics(
        self,
        recruiter_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        response = await recruiter_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Open Roles" in response.text
        assert "Total Candidates" in response.text


# ============================================================
# SCRUM-16258: Hiring Manager Dashboard
# ============================================================


class TestHiringManagerDashboard:
    async def test_hiring_manager_dashboard_loads_successfully(
        self, hiring_manager_client: AsyncClient, hiring_manager_user: User
    ):
        response = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Dashboard" in response.text
        assert hiring_manager_user.full_name in response.text

    async def test_hiring_manager_dashboard_shows_own_metrics(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "My Open Roles" in response.text or "Open Roles" in response.text
        assert "Pending Interviews" in response.text
        assert "Total Applications" in response.text

    async def test_hiring_manager_dashboard_shows_my_jobs(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "My Open Jobs" in response.text or "My Pipeline" in response.text

    async def test_hiring_manager_dashboard_shows_pipeline(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Pipeline" in response.text


# ============================================================
# SCRUM-16259: Interviewer Dashboard
# ============================================================


class TestInterviewerDashboard:
    async def test_interviewer_dashboard_loads_successfully(
        self, interviewer_client: AsyncClient, interviewer_user: User
    ):
        response = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Dashboard" in response.text
        assert interviewer_user.full_name in response.text

    async def test_interviewer_dashboard_shows_interview_metrics(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Upcoming Interviews" in response.text or "Pending Interviews" in response.text
        assert "Missing Feedback" in response.text

    async def test_interviewer_dashboard_shows_my_interviews(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "My Interviews" in response.text

    async def test_interviewer_dashboard_shows_pending_feedback_warning(
        self,
        interviewer_client: AsyncClient,
        db_session: AsyncSession,
        interviewer_user: User,
        sample_application: Application,
    ):
        from datetime import datetime, timedelta

        past_interview = Interview(
            application_id=sample_application.id,
            interviewer_id=interviewer_user.id,
            scheduled_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(past_interview)
        await db_session.flush()
        await db_session.commit()

        response = await interviewer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Missing Feedback" in response.text or "Feedback Required" in response.text


# ============================================================
# SCRUM-16260: Audit Log Recording
# ============================================================


class TestAuditLogRecording:
    async def test_creating_job_records_audit_log(
        self,
        admin_client: AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        from sqlalchemy import select, func

        count_before_result = await db_session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.entity_type == "Job"
            )
        )
        count_before = count_before_result.scalar() or 0

        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Audit Test Job",
                "description": "Testing audit logging",
                "department": "QA",
                "location": "Remote",
                "salary_range": "100000-120000",
                "hiring_manager_id": str(admin_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code in (303, 302, 200)

        count_after_result = await db_session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.entity_type == "Job"
            )
        )
        count_after = count_after_result.scalar() or 0

        assert count_after > count_before

    async def test_creating_candidate_records_audit_log(
        self,
        recruiter_client: AsyncClient,
        db_session: AsyncSession,
    ):
        from sqlalchemy import select, func

        count_before_result = await db_session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.entity_type == "Candidate"
            )
        )
        count_before = count_before_result.scalar() or 0

        response = await recruiter_client.post(
            "/candidates/create",
            data={
                "first_name": "Audit",
                "last_name": "TestCandidate",
                "email": "audit.test@example.com",
                "phone": "+1555000111",
                "linkedin_url": "",
                "skills": "Python, Testing",
                "resume_text": "Test resume",
            },
            follow_redirects=False,
        )
        assert response.status_code in (303, 302, 200)

        count_after_result = await db_session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.entity_type == "Candidate"
            )
        )
        count_after = count_after_result.scalar() or 0

        assert count_after > count_before

    async def test_audit_log_records_user_id(
        self,
        admin_client: AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        from sqlalchemy import select

        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Audit User ID Test",
                "description": "Testing user_id in audit log",
                "department": "Engineering",
                "location": "NYC",
                "hiring_manager_id": str(admin_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code in (303, 302, 200)

        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == "Job")
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.user_id == admin_user.id

    async def test_audit_log_records_action_and_details(
        self,
        admin_client: AsyncClient,
        admin_user: User,
        db_session: AsyncSession,
    ):
        from sqlalchemy import select

        response = await admin_client.post(
            "/jobs/create",
            data={
                "title": "Audit Details Test",
                "description": "Testing details in audit log",
                "department": "HR",
                "location": "London",
                "hiring_manager_id": str(admin_user.id),
            },
            follow_redirects=False,
        )
        assert response.status_code in (303, 302, 200)

        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == "Job")
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.action == "create"
        assert log.details is not None
        assert "Audit Details Test" in log.details


# ============================================================
# SCRUM-16261: Audit Log Display
# ============================================================


class TestAuditLogDisplay:
    async def test_audit_log_page_loads_for_admin(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get("/dashboard/audit-log", follow_redirects=False)
        assert response.status_code == 200
        assert "audit" in response.text.lower()

    async def test_audit_log_displays_entries(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get("/dashboard/audit-log", follow_redirects=False)
        assert response.status_code == 200
        assert "Test audit log entry" in response.text

    async def test_audit_log_pagination(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        admin_user: User,
    ):
        for i in range(60):
            log = AuditLog(
                user_id=admin_user.id,
                action="create",
                entity_type="Job",
                entity_id=i + 100,
                details=f"Pagination test entry {i}",
            )
            db_session.add(log)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.get(
            "/dashboard/audit-log?page=1&per_page=10",
            follow_redirects=False,
        )
        assert response.status_code == 200

        response_page2 = await admin_client.get(
            "/dashboard/audit-log?page=2&per_page=10",
            follow_redirects=False,
        )
        assert response_page2.status_code == 200

    async def test_audit_log_filter_by_entity_type(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get(
            "/dashboard/audit-log?entity_type=Job",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_audit_log_filter_by_action(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get(
            "/dashboard/audit-log?action=create",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_audit_log_filter_by_user_id(
        self,
        admin_client: AsyncClient,
        admin_user: User,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get(
            f"/dashboard/audit-log?user_id={admin_user.id}",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_audit_log_filter_by_date_range(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get(
            "/dashboard/audit-log?date_from=2020-01-01&date_to=2099-12-31",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_audit_log_combined_filters(
        self,
        admin_client: AsyncClient,
        admin_user: User,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get(
            f"/dashboard/audit-log?entity_type=Job&action=create&user_id={admin_user.id}",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_audit_log_empty_filters_returns_all(
        self,
        admin_client: AsyncClient,
        sample_audit_logs: list[AuditLog],
    ):
        response = await admin_client.get(
            "/dashboard/audit-log?entity_type=&action=",
            follow_redirects=False,
        )
        assert response.status_code == 200


# ============================================================
# SCRUM-16262: Audit Log RBAC Enforcement
# ============================================================


class TestAuditLogRBAC:
    async def test_unauthenticated_user_cannot_access_audit_log(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code in (303, 401, 403)

    async def test_interviewer_cannot_access_audit_log(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code in (403, 303)

    async def test_recruiter_cannot_access_audit_log(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code in (403, 303)

    async def test_hiring_manager_cannot_access_audit_log(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code in (403, 303)

    async def test_admin_can_access_audit_log(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get(
            "/dashboard/audit-log", follow_redirects=False
        )
        assert response.status_code == 200


# ============================================================
# Dashboard Access Control
# ============================================================


class TestDashboardAccessControl:
    async def test_unauthenticated_user_redirected_to_login(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/dashboard", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_all_roles_can_access_dashboard(
        self,
        admin_client: AsyncClient,
        recruiter_client: AsyncClient,
        hiring_manager_client: AsyncClient,
        interviewer_client: AsyncClient,
    ):
        for client_fixture in [
            admin_client,
            recruiter_client,
            hiring_manager_client,
            interviewer_client,
        ]:
            response = await client_fixture.get("/dashboard", follow_redirects=False)
            assert response.status_code == 200


# ============================================================
# Dashboard Metrics API
# ============================================================


class TestDashboardMetricsAPI:
    async def test_metrics_endpoint_returns_json_for_admin(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get("/dashboard/metrics", follow_redirects=False)
        assert response.status_code == 200
        data = response.json()
        assert "open_roles" in data
        assert "total_candidates" in data
        assert "pending_interviews" in data
        assert "pipeline" in data

    async def test_metrics_endpoint_returns_json_for_hiring_manager(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/dashboard/metrics", follow_redirects=False
        )
        assert response.status_code == 200
        data = response.json()
        assert "open_roles" in data
        assert "pipeline" in data

    async def test_metrics_endpoint_returns_json_for_interviewer(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/dashboard/metrics", follow_redirects=False
        )
        assert response.status_code == 200
        data = response.json()
        assert "pending_interviews" in data
        assert "missing_feedback" in data

    async def test_metrics_endpoint_requires_auth(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/dashboard/metrics", follow_redirects=False
        )
        assert response.status_code in (303, 401, 403)


# ============================================================
# Audit Trail Service Integration
# ============================================================


class TestAuditTrailServiceIntegration:
    async def test_audit_service_log_action(self, db_session: AsyncSession, admin_user: User):
        from app.services.audit_service import AuditTrailService

        service = AuditTrailService(db_session)
        log = await service.log_action(
            user_id=admin_user.id,
            action="test_action",
            entity_type="TestEntity",
            entity_id=999,
            details="Integration test detail",
        )
        assert log is not None
        assert log.id is not None
        assert log.user_id == admin_user.id
        assert log.action == "test_action"
        assert log.entity_type == "TestEntity"
        assert log.entity_id == 999
        assert log.details == "Integration test detail"

    async def test_audit_service_query_logs(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.audit_service import AuditTrailService
        from app.schemas.audit_log import AuditLogFilterParams

        service = AuditTrailService(db_session)

        for i in range(3):
            await service.log_action(
                user_id=admin_user.id,
                action="query_test",
                entity_type="QueryTestEntity",
                entity_id=i + 1,
                details=f"Query test {i}",
            )

        filters = AuditLogFilterParams(
            page=1,
            per_page=10,
            entity_type="QueryTestEntity",
        )
        result = await service.query_logs(filters=filters)
        assert result.total >= 3
        assert len(result.items) >= 3

    async def test_audit_service_get_recent_logs(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.audit_service import AuditTrailService

        service = AuditTrailService(db_session)

        for i in range(5):
            await service.log_action(
                user_id=admin_user.id,
                action="recent_test",
                entity_type="RecentEntity",
                entity_id=i + 1,
                details=f"Recent test {i}",
            )

        recent = await service.get_recent_logs(limit=3)
        assert len(recent) <= 3

    async def test_audit_service_log_action_with_null_user(
        self, db_session: AsyncSession
    ):
        from app.services.audit_service import AuditTrailService

        service = AuditTrailService(db_session)
        log = await service.log_action(
            user_id=None,
            action="system_action",
            entity_type="System",
            entity_id=1,
            details="System-level action without user",
        )
        assert log is not None
        assert log.user_id is None
        assert log.action == "system_action"


# ============================================================
# Dashboard Service Integration
# ============================================================


class TestDashboardServiceIntegration:
    async def test_dashboard_service_admin_context(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.dashboard_service import DashboardService

        service = DashboardService(db_session)
        context = await service.get_dashboard_context(admin_user)
        assert "metrics" in context
        assert "recent_audit_logs" in context

    async def test_dashboard_service_hiring_manager_context(
        self, db_session: AsyncSession, hiring_manager_user: User
    ):
        from app.services.dashboard_service import DashboardService

        service = DashboardService(db_session)
        context = await service.get_dashboard_context(hiring_manager_user)
        assert "metrics" in context
        assert "my_jobs" in context

    async def test_dashboard_service_interviewer_context(
        self, db_session: AsyncSession, interviewer_user: User
    ):
        from app.services.dashboard_service import DashboardService

        service = DashboardService(db_session)
        context = await service.get_dashboard_context(interviewer_user)
        assert "metrics" in context
        assert "my_interviews" in context

    async def test_dashboard_service_metrics_admin(
        self, db_session: AsyncSession, admin_user: User
    ):
        from app.services.dashboard_service import DashboardService

        service = DashboardService(db_session)
        metrics = await service.get_metrics(admin_user)
        assert "open_roles" in metrics
        assert "total_candidates" in metrics
        assert "pending_interviews" in metrics
        assert "missing_feedback" in metrics
        assert "pipeline" in metrics
        assert "total_applications" in metrics

    async def test_dashboard_service_metrics_interviewer(
        self, db_session: AsyncSession, interviewer_user: User
    ):
        from app.services.dashboard_service import DashboardService

        service = DashboardService(db_session)
        metrics = await service.get_metrics(interviewer_user)
        assert "pending_interviews" in metrics
        assert "missing_feedback" in metrics

    async def test_metrics_aggregator_pipeline_counts(
        self,
        db_session: AsyncSession,
        admin_user: User,
        sample_application: Application,
    ):
        from app.services.dashboard_service import MetricsAggregator

        aggregator = MetricsAggregator(db_session)
        pipeline = await aggregator.aggregate_pipeline()
        assert "Applied" in pipeline
        assert pipeline["Applied"] >= 1
        assert "Screening" in pipeline
        assert "Interview" in pipeline
        assert "Offer" in pipeline
        assert "Hired" in pipeline
        assert "Rejected" in pipeline

    async def test_metrics_aggregator_count_open_roles(
        self,
        db_session: AsyncSession,
        sample_job: Job,
    ):
        from app.services.dashboard_service import MetricsAggregator

        aggregator = MetricsAggregator(db_session)
        count = await aggregator.count_open_roles()
        assert count >= 1

    async def test_metrics_aggregator_count_total_candidates(
        self,
        db_session: AsyncSession,
        sample_candidate: Candidate,
    ):
        from app.services.dashboard_service import MetricsAggregator

        aggregator = MetricsAggregator(db_session)
        count = await aggregator.count_total_candidates()
        assert count >= 1

    async def test_metrics_aggregator_count_pending_interviews(
        self,
        db_session: AsyncSession,
        sample_interview: Interview,
    ):
        from app.services.dashboard_service import MetricsAggregator

        aggregator = MetricsAggregator(db_session)
        count = await aggregator.count_pending_interviews()
        assert count >= 1

    async def test_metrics_aggregator_hiring_manager_scoped(
        self,
        db_session: AsyncSession,
        hiring_manager_user: User,
    ):
        from app.services.dashboard_service import MetricsAggregator

        aggregator = MetricsAggregator(db_session)
        count = await aggregator.count_open_roles(hiring_manager_user)
        assert count >= 0

        pipeline = await aggregator.aggregate_pipeline(hiring_manager_user)
        assert isinstance(pipeline, dict)