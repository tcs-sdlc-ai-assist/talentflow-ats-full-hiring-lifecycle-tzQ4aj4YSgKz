import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession, admin_user: User) -> Job:
    job = Job(
        title="Backend Engineer",
        description="Build APIs and services",
        department="Engineering",
        location="Remote",
        salary_range="100000-150000",
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
        first_name="Alice",
        last_name="Smith",
        email="alice.smith@example.com",
        phone="+1234567890",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    await db_session.commit()
    return candidate


@pytest_asyncio.fixture
async def second_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="Bob",
        last_name="Jones",
        email="bob.jones@example.com",
        phone="+0987654321",
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


class TestApplicationList:
    async def test_list_applications_requires_auth(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_list_applications_authenticated(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get("/applications", follow_redirects=False)
        assert response.status_code == 200
        assert b"Applications" in response.content

    async def test_list_applications_with_status_filter(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            "/applications?status=Applied", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Alice" in response.content or b"Applied" in response.content

    async def test_list_applications_with_job_filter(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_job: Job,
    ):
        response = await admin_client.get(
            f"/applications?job_id={sample_job.id}", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_list_applications_empty_filter_returns_all(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            "/applications?status=Hired", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_list_applications_interviewer_can_view(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
    ):
        response = await interviewer_client.get(
            "/applications", follow_redirects=False
        )
        assert response.status_code == 200


class TestApplicationCreate:
    async def test_create_application_form_requires_admin_or_recruiter(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code in (403, 303)

    async def test_create_application_form_accessible_by_admin(
        self, admin_client: AsyncClient, sample_job: Job, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_create_application_form_accessible_by_recruiter(
        self,
        recruiter_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        response = await recruiter_client.get(
            "/applications/create", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_create_application_success(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": str(sample_job.id),
                "candidate_id": str(sample_candidate.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/applications/" in location

    async def test_create_application_duplicate_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": str(sample_job.id),
                "candidate_id": str(sample_candidate.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_invalid_job_rejected(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": "99999",
                "candidate_id": str(sample_candidate.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_invalid_candidate_rejected(
        self,
        admin_client: AsyncClient,
        sample_job: Job,
    ):
        response = await admin_client.post(
            "/applications/create",
            data={
                "job_id": str(sample_job.id),
                "candidate_id": "99999",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_create_application_hiring_manager_forbidden(
        self,
        hiring_manager_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        response = await hiring_manager_client.post(
            "/applications/create",
            data={
                "job_id": str(sample_job.id),
                "candidate_id": str(sample_candidate.id),
            },
            follow_redirects=False,
        )
        assert response.status_code in (403, 303)

    async def test_create_application_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
        sample_job: Job,
        sample_candidate: Candidate,
    ):
        response = await interviewer_client.post(
            "/applications/create",
            data={
                "job_id": str(sample_job.id),
                "candidate_id": str(sample_candidate.id),
            },
            follow_redirects=False,
        )
        assert response.status_code in (403, 303)


class TestApplicationDetail:
    async def test_application_detail_requires_auth(
        self,
        unauthenticated_client: AsyncClient,
        sample_application: Application,
    ):
        response = await unauthenticated_client.get(
            f"/applications/{sample_application.id}", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_application_detail_success(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            f"/applications/{sample_application.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Application #" in response.content

    async def test_application_detail_not_found(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get(
            "/applications/99999", follow_redirects=False
        )
        assert response.status_code == 404

    async def test_application_detail_shows_candidate_info(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            f"/applications/{sample_application.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Alice" in response.content or b"Smith" in response.content

    async def test_application_detail_shows_job_info(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            f"/applications/{sample_application.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Backend Engineer" in response.content

    async def test_application_detail_shows_allowed_transitions(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            f"/applications/{sample_application.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Screening" in response.content


class TestApplicationStatusTransitions:
    async def test_valid_transition_applied_to_screening(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_valid_transition_applied_to_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_valid_transition_applied_to_withdrawn(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Withdrawn"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_invalid_transition_applied_to_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_invalid_transition_applied_to_offer(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Offer"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_invalid_transition_applied_to_interview(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Interview"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_valid_transition_screening_to_interview(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        sample_application.status = "Screening"
        db_session.add(sample_application)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Interview"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_valid_transition_interview_to_offer(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        sample_application.status = "Interview"
        db_session.add(sample_application)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Offer"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_valid_transition_offer_to_hired(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        sample_application.status = "Offer"
        db_session.add(sample_application)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Hired"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_terminal_state_hired_no_transitions(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        sample_application.status = "Hired"
        db_session.add(sample_application)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_terminal_state_rejected_no_transitions(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        sample_application.status = "Rejected"
        db_session.add(sample_application)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Applied"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_terminal_state_withdrawn_no_transitions(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
    ):
        sample_application.status = "Withdrawn"
        db_session.add(sample_application)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Applied"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_invalid_status_value_rejected(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "InvalidStatus"},
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_status_update_nonexistent_application(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.post(
            "/applications/99999/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestApplicationStatusRBAC:
    async def test_admin_can_update_status(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_recruiter_can_update_status(
        self,
        recruiter_client: AsyncClient,
        sample_application: Application,
    ):
        response = await recruiter_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_hiring_manager_can_update_status(
        self,
        hiring_manager_client: AsyncClient,
        sample_application: Application,
    ):
        response = await hiring_manager_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_interviewer_cannot_update_status(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
    ):
        response = await interviewer_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code in (403, 303)

    async def test_unauthenticated_cannot_update_status(
        self,
        unauthenticated_client: AsyncClient,
        sample_application: Application,
    ):
        response = await unauthenticated_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code in (403, 303)


class TestApplicationPipeline:
    async def test_pipeline_view_requires_auth(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_pipeline_view_accessible_by_admin(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 200
        assert b"Pipeline" in response.content

    async def test_pipeline_view_shows_all_stages(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 200
        content = response.content
        assert b"Applied" in content
        assert b"Screening" in content
        assert b"Interview" in content
        assert b"Offer" in content
        assert b"Hired" in content
        assert b"Rejected" in content

    async def test_pipeline_view_groups_applications_by_status(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: Job,
        sample_candidate: Candidate,
        second_candidate: Candidate,
    ):
        app1 = Application(
            job_id=sample_job.id,
            candidate_id=sample_candidate.id,
            status="Applied",
        )
        app2 = Application(
            job_id=sample_job.id,
            candidate_id=second_candidate.id,
            status="Screening",
        )
        db_session.add(app1)
        db_session.add(app2)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 200
        content = response.content
        assert b"Alice" in content or b"Smith" in content
        assert b"Bob" in content or b"Jones" in content

    async def test_pipeline_view_filter_by_job(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_job: Job,
    ):
        response = await admin_client.get(
            f"/applications/pipeline?job_id={sample_job.id}",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_pipeline_view_filter_by_nonexistent_job(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get(
            "/applications/pipeline?job_id=99999",
            follow_redirects=False,
        )
        assert response.status_code == 200

    async def test_pipeline_view_accessible_by_recruiter(
        self,
        recruiter_client: AsyncClient,
    ):
        response = await recruiter_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_pipeline_view_accessible_by_hiring_manager(
        self,
        hiring_manager_client: AsyncClient,
    ):
        response = await hiring_manager_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 200

    async def test_pipeline_view_accessible_by_interviewer(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get(
            "/applications/pipeline", follow_redirects=False
        )
        assert response.status_code == 200


class TestAllowedTransitionsCompleteness:
    """Verify that ALLOWED_TRANSITIONS covers all expected status flows."""

    async def test_allowed_transitions_from_applied(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert set(ALLOWED_TRANSITIONS["Applied"]) == {
            "Screening",
            "Rejected",
            "Withdrawn",
        }

    async def test_allowed_transitions_from_screening(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert set(ALLOWED_TRANSITIONS["Screening"]) == {
            "Interview",
            "Rejected",
            "Withdrawn",
        }

    async def test_allowed_transitions_from_interview(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert set(ALLOWED_TRANSITIONS["Interview"]) == {
            "Offer",
            "Rejected",
            "Withdrawn",
        }

    async def test_allowed_transitions_from_offer(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert set(ALLOWED_TRANSITIONS["Offer"]) == {
            "Hired",
            "Rejected",
            "Withdrawn",
        }

    async def test_allowed_transitions_from_hired_is_empty(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert ALLOWED_TRANSITIONS["Hired"] == []

    async def test_allowed_transitions_from_rejected_is_empty(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert ALLOWED_TRANSITIONS["Rejected"] == []

    async def test_allowed_transitions_from_withdrawn_is_empty(self):
        from app.schemas.application import ALLOWED_TRANSITIONS

        assert ALLOWED_TRANSITIONS["Withdrawn"] == []

    async def test_all_statuses_have_transition_entries(self):
        from app.schemas.application import ALLOWED_TRANSITIONS, APPLICATION_STATUSES

        for status in APPLICATION_STATUSES:
            assert status in ALLOWED_TRANSITIONS, (
                f"Status '{status}' missing from ALLOWED_TRANSITIONS"
            )


class TestApplicationStatusUpdateRedirect:
    async def test_status_update_redirects_to_detail(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert f"/applications/{sample_application.id}" in location

    async def test_status_update_from_pipeline_redirects_to_pipeline(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            headers={"referer": "http://testserver/applications/pipeline"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/applications/pipeline" in location

    async def test_status_update_from_pipeline_with_job_filter_preserves_filter(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        sample_job: Job,
    ):
        response = await admin_client.post(
            f"/applications/{sample_application.id}/status",
            data={"status": "Screening"},
            headers={
                "referer": f"http://testserver/applications/pipeline?job_id={sample_job.id}"
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/applications/pipeline" in location
        assert f"job_id={sample_job.id}" in location


class TestApplicationMultiStepTransition:
    async def test_full_pipeline_applied_to_hired(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        transitions = ["Screening", "Interview", "Offer", "Hired"]
        for new_status in transitions:
            response = await admin_client.post(
                f"/applications/{sample_application.id}/status",
                data={"status": new_status},
                follow_redirects=False,
            )
            assert response.status_code == 303, (
                f"Failed transition to {new_status}: got {response.status_code}"
            )

    async def test_full_pipeline_applied_to_rejected_at_screening(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: Job,
        second_candidate: Candidate,
    ):
        app = Application(
            job_id=sample_job.id,
            candidate_id=second_candidate.id,
            status="Applied",
        )
        db_session.add(app)
        await db_session.flush()
        await db_session.refresh(app)
        await db_session.commit()

        response = await admin_client.post(
            f"/applications/{app.id}/status",
            data={"status": "Screening"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        response = await admin_client.post(
            f"/applications/{app.id}/status",
            data={"status": "Rejected"},
            follow_redirects=False,
        )
        assert response.status_code == 303