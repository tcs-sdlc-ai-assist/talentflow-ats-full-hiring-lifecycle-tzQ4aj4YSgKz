import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.application import Application
from app.models.interview import Interview
from app.core.security import get_password_hash, create_session_cookie, COOKIE_NAME


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
        last_name="Johnson",
        email="alice.johnson@example.com",
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
        status="Interview",
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
    interview = Interview(
        application_id=sample_application.id,
        interviewer_id=interviewer_user.id,
        scheduled_at=datetime.utcnow() + timedelta(days=2),
    )
    db_session.add(interview)
    await db_session.flush()
    await db_session.refresh(interview)
    await db_session.commit()
    return interview


@pytest_asyncio.fixture
async def second_interviewer_user(db_session: AsyncSession) -> User:
    user = User(
        username="secondinterviewer",
        password_hash=get_password_hash("interviewerpass123"),
        full_name="Second Interviewer",
        role="Interviewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


class TestListInterviews:
    async def test_list_interviews_authenticated(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await admin_client.get("/interviews")
        assert response.status_code == 200
        assert "Interviews" in response.text
        assert f"Application #{sample_interview.application_id}" in response.text

    async def test_list_interviews_unauthenticated_redirects(
        self,
        unauthenticated_client: AsyncClient,
    ):
        response = await unauthenticated_client.get(
            "/interviews", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_list_interviews_empty(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/interviews")
        assert response.status_code == 200
        assert "No interviews scheduled" in response.text


class TestScheduleInterview:
    async def test_schedule_interview_form_admin(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        response = await admin_client.get(
            f"/interviews/schedule?application_id={sample_application.id}"
        )
        assert response.status_code == 200
        assert "Schedule" in response.text

    async def test_schedule_interview_form_recruiter(
        self,
        recruiter_client: AsyncClient,
        sample_application: Application,
    ):
        response = await recruiter_client.get("/interviews/schedule")
        assert response.status_code == 200

    async def test_schedule_interview_form_hiring_manager(
        self,
        hiring_manager_client: AsyncClient,
        sample_application: Application,
    ):
        response = await hiring_manager_client.get("/interviews/schedule")
        assert response.status_code == 200

    async def test_schedule_interview_submit_success(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=3)).isoformat()
        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/interviews/" in location

    async def test_schedule_interview_invalid_date(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": "not-a-date",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "Invalid date" in response.text

    async def test_schedule_interview_invalid_application(
        self,
        admin_client: AsyncClient,
        interviewer_user: User,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=3)).isoformat()
        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": "99999",
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_invalid_interviewer(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=3)).isoformat()
        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": "99999",
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

    async def test_schedule_interview_rbac_interviewer_denied(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code in (303, 403)


class TestInterviewDetail:
    async def test_interview_detail_authenticated(
        self,
        admin_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await admin_client.get(f"/interviews/{sample_interview.id}")
        assert response.status_code == 200
        assert "Interview" in response.text

    async def test_interview_detail_not_found(
        self,
        admin_client: AsyncClient,
    ):
        response = await admin_client.get("/interviews/99999")
        assert response.status_code == 404

    async def test_interview_detail_unauthenticated_redirects(
        self,
        unauthenticated_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await unauthenticated_client.get(
            f"/interviews/{sample_interview.id}", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")


class TestFeedbackForm:
    async def test_feedback_form_get(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await interviewer_client.get(
            f"/interviews/{sample_interview.id}/feedback"
        )
        assert response.status_code == 200
        assert "Feedback" in response.text

    async def test_feedback_form_not_found(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/interviews/99999/feedback")
        assert response.status_code == 404


class TestSubmitFeedback:
    async def test_submit_feedback_success(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": "4",
                "notes": "Great candidate with strong technical skills.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert f"/interviews/{sample_interview.id}" in location

    async def test_submit_feedback_rating_5_no_notes(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await interviewer_client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": "5",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_submit_feedback_low_rating_requires_notes(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
        interviewer_user: User,
    ):
        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=interviewer_user.id,
            scheduled_at=datetime.utcnow() + timedelta(days=1),
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(interviewer_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)

        response = await client.post(
            f"/interviews/{interview.id}/feedback",
            data={
                "rating": "1",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "required" in response.text.lower() or "notes" in response.text.lower()

        client.cookies.clear()

    async def test_submit_feedback_low_rating_with_notes_succeeds(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
        interviewer_user: User,
    ):
        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=interviewer_user.id,
            scheduled_at=datetime.utcnow() + timedelta(days=1),
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(interviewer_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)

        response = await client.post(
            f"/interviews/{interview.id}/feedback",
            data={
                "rating": "2",
                "notes": "Candidate needs improvement in system design.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        client.cookies.clear()

    async def test_submit_feedback_wrong_interviewer(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_interview: Interview,
        second_interviewer_user: User,
    ):
        cookie_value = create_session_cookie(second_interviewer_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)

        response = await client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": "4",
                "notes": "Good candidate.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "assigned" in response.text.lower() or "interviewer" in response.text.lower()

        client.cookies.clear()

    async def test_submit_feedback_already_submitted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
        interviewer_user: User,
    ):
        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=interviewer_user.id,
            scheduled_at=datetime.utcnow() + timedelta(days=1),
            feedback_rating=4,
            feedback_notes="Already submitted.",
            feedback_submitted_at=datetime.utcnow(),
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(interviewer_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)

        response = await client.post(
            f"/interviews/{interview.id}/feedback",
            data={
                "rating": "5",
                "notes": "Trying to submit again.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already" in response.text.lower()

        client.cookies.clear()

    async def test_submit_feedback_not_found(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.post(
            "/interviews/99999/feedback",
            data={
                "rating": "3",
                "notes": "Some notes.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 404

    async def test_submit_feedback_unauthenticated_redirects(
        self,
        unauthenticated_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await unauthenticated_client.post(
            f"/interviews/{sample_interview.id}/feedback",
            data={
                "rating": "4",
                "notes": "Good.",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")


class TestMyInterviews:
    async def test_my_interviews_shows_assigned(
        self,
        interviewer_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await interviewer_client.get("/interviews/my")
        assert response.status_code == 200
        assert "My Interviews" in response.text
        assert "Pending" in response.text or "Submit Feedback" in response.text

    async def test_my_interviews_empty_for_other_user(
        self,
        client: AsyncClient,
        second_interviewer_user: User,
        sample_interview: Interview,
    ):
        cookie_value = create_session_cookie(second_interviewer_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)

        response = await client.get("/interviews/my")
        assert response.status_code == 200
        assert "No interviews assigned" in response.text or "All feedback submitted" in response.text

        client.cookies.clear()

    async def test_my_interviews_shows_completed_feedback(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_application: Application,
        interviewer_user: User,
    ):
        interview = Interview(
            application_id=sample_application.id,
            interviewer_id=interviewer_user.id,
            scheduled_at=datetime.utcnow() - timedelta(days=1),
            feedback_rating=5,
            feedback_notes="Excellent candidate.",
            feedback_submitted_at=datetime.utcnow(),
        )
        db_session.add(interview)
        await db_session.flush()
        await db_session.refresh(interview)
        await db_session.commit()

        cookie_value = create_session_cookie(interviewer_user.id)
        client.cookies.set(COOKIE_NAME, cookie_value)

        response = await client.get("/interviews/my")
        assert response.status_code == 200
        assert "Completed" in response.text or "Submitted" in response.text

        client.cookies.clear()


class TestInterviewRBAC:
    async def test_schedule_form_denied_for_interviewer(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get(
            "/interviews/schedule", follow_redirects=False
        )
        assert response.status_code in (303, 403)

    async def test_schedule_submit_denied_for_interviewer(
        self,
        interviewer_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=3)).isoformat()
        response = await interviewer_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code in (303, 403)

    async def test_admin_can_schedule(
        self,
        admin_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=5)).isoformat()
        response = await admin_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_recruiter_can_schedule(
        self,
        recruiter_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=6)).isoformat()
        response = await recruiter_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_hiring_manager_can_schedule(
        self,
        hiring_manager_client: AsyncClient,
        sample_application: Application,
        interviewer_user: User,
    ):
        scheduled_time = (datetime.utcnow() + timedelta(days=7)).isoformat()
        response = await hiring_manager_client.post(
            "/interviews/schedule",
            data={
                "application_id": str(sample_application.id),
                "interviewer_id": str(interviewer_user.id),
                "scheduled_at": scheduled_time,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_any_authenticated_user_can_view_interviews(
        self,
        interviewer_client: AsyncClient,
    ):
        response = await interviewer_client.get("/interviews")
        assert response.status_code == 200

    async def test_any_authenticated_user_can_view_detail(
        self,
        recruiter_client: AsyncClient,
        sample_interview: Interview,
    ):
        response = await recruiter_client.get(f"/interviews/{sample_interview.id}")
        assert response.status_code == 200