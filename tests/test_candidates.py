import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_session_cookie, COOKIE_NAME
from app.models.candidate import Candidate, Skill
from app.models.job import Job
from app.models.application import Application
from app.models.user import User
from app.core.security import get_password_hash


@pytest_asyncio.fixture
async def sample_candidate(db_session: AsyncSession) -> Candidate:
    candidate = Candidate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1 555-123-4567",
        linkedin_url="https://linkedin.com/in/janedoe",
        resume_text="Experienced software engineer with 5 years of Python development.",
    )
    db_session.add(candidate)
    await db_session.flush()
    await db_session.refresh(candidate)
    await db_session.commit()
    return candidate


@pytest_asyncio.fixture
async def sample_skill(db_session: AsyncSession) -> Skill:
    skill = Skill(name="Python")
    db_session.add(skill)
    await db_session.flush()
    await db_session.refresh(skill)
    await db_session.commit()
    return skill


@pytest_asyncio.fixture
async def candidate_with_skill(
    db_session: AsyncSession, sample_candidate: Candidate, sample_skill: Skill
) -> Candidate:
    sample_candidate.skills.append(sample_skill)
    await db_session.flush()
    await db_session.refresh(sample_candidate)
    await db_session.commit()
    return sample_candidate


@pytest_asyncio.fixture
async def candidate_with_application(
    db_session: AsyncSession,
    sample_candidate: Candidate,
    admin_user: User,
) -> tuple[Candidate, Application, Job]:
    job = Job(
        title="Senior Python Developer",
        description="Build amazing things with Python.",
        department="Engineering",
        location="Remote",
        salary_range="120000-150000",
        hiring_manager_id=admin_user.id,
        status="Open",
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    application = Application(
        job_id=job.id,
        candidate_id=sample_candidate.id,
        status="Applied",
    )
    db_session.add(application)
    await db_session.flush()
    await db_session.refresh(application)
    await db_session.commit()

    return sample_candidate, application, job


class TestListCandidates:
    async def test_list_candidates_authenticated(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text
        assert "jane.doe@example.com" in response.text

    async def test_list_candidates_unauthenticated_redirects(
        self, unauthenticated_client: AsyncClient
    ):
        response = await unauthenticated_client.get(
            "/candidates", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_list_candidates_empty(self, admin_client: AsyncClient):
        response = await admin_client.get("/candidates", follow_redirects=False)
        assert response.status_code == 200
        assert "No candidates found" in response.text

    async def test_list_candidates_search_by_name(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            "/candidates?search=Jane", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text

    async def test_list_candidates_search_by_email(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            "/candidates?search=jane.doe", follow_redirects=False
        )
        assert response.status_code == 200
        assert "jane.doe@example.com" in response.text

    async def test_list_candidates_search_no_results(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            "/candidates?search=nonexistent", follow_redirects=False
        )
        assert response.status_code == 200
        assert "No candidates found" in response.text

    async def test_list_candidates_search_by_skill(
        self, admin_client: AsyncClient, candidate_with_skill: Candidate
    ):
        response = await admin_client.get(
            "/candidates?search=Python", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text

    async def test_list_candidates_interviewer_can_view(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await interviewer_client.get(
            "/candidates", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text

    async def test_list_candidates_hiring_manager_can_view(
        self, hiring_manager_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await hiring_manager_client.get(
            "/candidates", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text


class TestCreateCandidate:
    async def test_create_candidate_form_admin(self, admin_client: AsyncClient):
        response = await admin_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Create New Candidate" in response.text

    async def test_create_candidate_form_recruiter(
        self, recruiter_client: AsyncClient
    ):
        response = await recruiter_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Create New Candidate" in response.text

    async def test_create_candidate_form_interviewer_forbidden(
        self, interviewer_client: AsyncClient
    ):
        response = await interviewer_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_create_candidate_form_hiring_manager_forbidden(
        self, hiring_manager_client: AsyncClient
    ):
        response = await hiring_manager_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_create_candidate_submit_success(
        self, admin_client: AsyncClient
    ):
        form_data = {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@example.com",
            "phone": "+1 555-987-6543",
            "linkedin_url": "https://linkedin.com/in/johnsmith",
            "skills": "Python, FastAPI, SQL",
            "resume_text": "Full stack developer with 3 years experience.",
        }
        response = await admin_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/candidates/" in location

    async def test_create_candidate_submit_minimal(
        self, admin_client: AsyncClient
    ):
        form_data = {
            "first_name": "Alice",
            "last_name": "Wonder",
            "email": "alice.wonder@example.com",
        }
        response = await admin_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/candidates/" in location

    async def test_create_candidate_duplicate_email(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {
            "first_name": "Another",
            "last_name": "Person",
            "email": "jane.doe@example.com",
        }
        response = await admin_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 422
        assert "already exists" in response.text

    async def test_create_candidate_recruiter_can_submit(
        self, recruiter_client: AsyncClient
    ):
        form_data = {
            "first_name": "Bob",
            "last_name": "Builder",
            "email": "bob.builder@example.com",
        }
        response = await recruiter_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 303

    async def test_create_candidate_interviewer_forbidden(
        self, interviewer_client: AsyncClient
    ):
        form_data = {
            "first_name": "Blocked",
            "last_name": "User",
            "email": "blocked@example.com",
        }
        response = await interviewer_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 403

    async def test_create_candidate_unauthenticated_redirects(
        self, unauthenticated_client: AsyncClient
    ):
        form_data = {
            "first_name": "Anon",
            "last_name": "User",
            "email": "anon@example.com",
        }
        response = await unauthenticated_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_create_candidate_with_skills(
        self, admin_client: AsyncClient
    ):
        form_data = {
            "first_name": "Skilled",
            "last_name": "Dev",
            "email": "skilled.dev@example.com",
            "skills": "React, TypeScript, Node.js",
        }
        response = await admin_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "/candidates/" in location

        detail_response = await admin_client.get(location, follow_redirects=False)
        assert detail_response.status_code == 200
        assert "React" in detail_response.text
        assert "TypeScript" in detail_response.text


class TestCandidateDetail:
    async def test_candidate_detail_authenticated(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text
        assert "Doe" in response.text
        assert "jane.doe@example.com" in response.text
        assert "+1 555-123-4567" in response.text

    async def test_candidate_detail_unauthenticated_redirects(
        self, unauthenticated_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await unauthenticated_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    async def test_candidate_detail_not_found(self, admin_client: AsyncClient):
        response = await admin_client.get(
            "/candidates/99999", follow_redirects=False
        )
        assert response.status_code == 404

    async def test_candidate_detail_shows_skills(
        self, admin_client: AsyncClient, candidate_with_skill: Candidate
    ):
        response = await admin_client.get(
            f"/candidates/{candidate_with_skill.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Python" in response.text

    async def test_candidate_detail_shows_applications(
        self,
        admin_client: AsyncClient,
        candidate_with_application: tuple[Candidate, Application, Job],
    ):
        candidate, application, job = candidate_with_application
        response = await admin_client.get(
            f"/candidates/{candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Senior Python Developer" in response.text
        assert "Applied" in response.text

    async def test_candidate_detail_shows_resume(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Experienced software engineer" in response.text

    async def test_candidate_detail_shows_linkedin(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "linkedin.com/in/janedoe" in response.text

    async def test_candidate_detail_interviewer_can_view(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await interviewer_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Jane" in response.text


class TestEditCandidate:
    async def test_edit_candidate_form_admin(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Edit Candidate" in response.text
        assert "Jane" in response.text

    async def test_edit_candidate_form_recruiter(
        self, recruiter_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await recruiter_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Edit Candidate" in response.text

    async def test_edit_candidate_form_interviewer_forbidden(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await interviewer_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert response.status_code == 403

    async def test_edit_candidate_form_not_found(
        self, admin_client: AsyncClient
    ):
        response = await admin_client.get(
            "/candidates/99999/edit", follow_redirects=False
        )
        assert response.status_code == 303
        assert "/candidates" in response.headers.get("location", "")

    async def test_edit_candidate_submit_success(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {
            "first_name": "Janet",
            "last_name": "Doe",
            "email": "janet.doe@example.com",
            "phone": "+1 555-000-0000",
            "linkedin_url": "https://linkedin.com/in/janetdoe",
            "skills": "Python, Django",
            "resume_text": "Updated resume text.",
        }
        response = await admin_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert f"/candidates/{sample_candidate.id}" in location

        detail_response = await admin_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_response.status_code == 200
        assert "Janet" in detail_response.text
        assert "janet.doe@example.com" in detail_response.text

    async def test_edit_candidate_submit_recruiter(
        self, recruiter_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {
            "first_name": "Jane",
            "last_name": "Updated",
            "email": "jane.doe@example.com",
        }
        response = await recruiter_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_edit_candidate_submit_interviewer_forbidden(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {
            "first_name": "Blocked",
            "last_name": "Edit",
            "email": "blocked.edit@example.com",
        }
        response = await interviewer_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_edit_candidate_duplicate_email(
        self,
        admin_client: AsyncClient,
        sample_candidate: Candidate,
        db_session: AsyncSession,
    ):
        other_candidate = Candidate(
            first_name="Other",
            last_name="Person",
            email="other.person@example.com",
        )
        db_session.add(other_candidate)
        await db_session.flush()
        await db_session.refresh(other_candidate)
        await db_session.commit()

        form_data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "other.person@example.com",
        }
        response = await admin_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "already exists" in response.text

    async def test_edit_candidate_update_skills(
        self, admin_client: AsyncClient, candidate_with_skill: Candidate
    ):
        form_data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "skills": "JavaScript, React, Vue",
        }
        response = await admin_client.post(
            f"/candidates/{candidate_with_skill.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303

        detail_response = await admin_client.get(
            f"/candidates/{candidate_with_skill.id}", follow_redirects=False
        )
        assert detail_response.status_code == 200
        assert "JavaScript" in detail_response.text
        assert "React" in detail_response.text

    async def test_edit_candidate_clear_skills(
        self, admin_client: AsyncClient, candidate_with_skill: Candidate
    ):
        form_data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "skills": "",
        }
        response = await admin_client.post(
            f"/candidates/{candidate_with_skill.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestSkillTagging:
    async def test_add_skill_to_candidate(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {"skill_name": "FastAPI"}
        response = await admin_client.post(
            f"/candidates/{sample_candidate.id}/skills",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/candidates/{sample_candidate.id}" in response.headers.get(
            "location", ""
        )

        detail_response = await admin_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_response.status_code == 200
        assert "FastAPI" in detail_response.text

    async def test_add_skill_recruiter(
        self, recruiter_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {"skill_name": "Docker"}
        response = await recruiter_client.post(
            f"/candidates/{sample_candidate.id}/skills",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_add_skill_interviewer_forbidden(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {"skill_name": "Blocked"}
        response = await interviewer_client.post(
            f"/candidates/{sample_candidate.id}/skills",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_add_duplicate_skill_no_error(
        self, admin_client: AsyncClient, candidate_with_skill: Candidate
    ):
        form_data = {"skill_name": "Python"}
        response = await admin_client.post(
            f"/candidates/{candidate_with_skill.id}/skills",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_add_skill_case_insensitive(
        self, admin_client: AsyncClient, candidate_with_skill: Candidate
    ):
        form_data = {"skill_name": "python"}
        response = await admin_client.post(
            f"/candidates/{candidate_with_skill.id}/skills",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_remove_skill_from_candidate(
        self,
        admin_client: AsyncClient,
        candidate_with_skill: Candidate,
        sample_skill: Skill,
    ):
        response = await admin_client.post(
            f"/candidates/{candidate_with_skill.id}/skills/{sample_skill.id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/candidates/{candidate_with_skill.id}" in response.headers.get(
            "location", ""
        )

    async def test_remove_skill_recruiter(
        self,
        recruiter_client: AsyncClient,
        candidate_with_skill: Candidate,
        sample_skill: Skill,
    ):
        response = await recruiter_client.post(
            f"/candidates/{candidate_with_skill.id}/skills/{sample_skill.id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_remove_skill_interviewer_forbidden(
        self,
        interviewer_client: AsyncClient,
        candidate_with_skill: Candidate,
        sample_skill: Skill,
    ):
        response = await interviewer_client.post(
            f"/candidates/{candidate_with_skill.id}/skills/{sample_skill.id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_remove_nonexistent_skill_redirects(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        response = await admin_client.post(
            f"/candidates/{sample_candidate.id}/skills/99999/remove",
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestCandidateRBAC:
    async def test_admin_full_access(
        self, admin_client: AsyncClient, sample_candidate: Candidate
    ):
        list_resp = await admin_client.get("/candidates", follow_redirects=False)
        assert list_resp.status_code == 200

        detail_resp = await admin_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_resp.status_code == 200

        create_form_resp = await admin_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert create_form_resp.status_code == 200

        edit_form_resp = await admin_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert edit_form_resp.status_code == 200

    async def test_recruiter_full_access(
        self, recruiter_client: AsyncClient, sample_candidate: Candidate
    ):
        list_resp = await recruiter_client.get(
            "/candidates", follow_redirects=False
        )
        assert list_resp.status_code == 200

        detail_resp = await recruiter_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_resp.status_code == 200

        create_form_resp = await recruiter_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert create_form_resp.status_code == 200

        edit_form_resp = await recruiter_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert edit_form_resp.status_code == 200

    async def test_hiring_manager_read_only(
        self, hiring_manager_client: AsyncClient, sample_candidate: Candidate
    ):
        list_resp = await hiring_manager_client.get(
            "/candidates", follow_redirects=False
        )
        assert list_resp.status_code == 200

        detail_resp = await hiring_manager_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_resp.status_code == 200

        create_form_resp = await hiring_manager_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert create_form_resp.status_code == 403

        edit_form_resp = await hiring_manager_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert edit_form_resp.status_code == 403

    async def test_interviewer_read_only(
        self, interviewer_client: AsyncClient, sample_candidate: Candidate
    ):
        list_resp = await interviewer_client.get(
            "/candidates", follow_redirects=False
        )
        assert list_resp.status_code == 200

        detail_resp = await interviewer_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_resp.status_code == 200

        create_form_resp = await interviewer_client.get(
            "/candidates/create", follow_redirects=False
        )
        assert create_form_resp.status_code == 403

        edit_form_resp = await interviewer_client.get(
            f"/candidates/{sample_candidate.id}/edit", follow_redirects=False
        )
        assert edit_form_resp.status_code == 403

    async def test_unauthenticated_no_access(
        self, unauthenticated_client: AsyncClient, sample_candidate: Candidate
    ):
        list_resp = await unauthenticated_client.get(
            "/candidates", follow_redirects=False
        )
        assert list_resp.status_code == 303

        detail_resp = await unauthenticated_client.get(
            f"/candidates/{sample_candidate.id}", follow_redirects=False
        )
        assert detail_resp.status_code == 303

    async def test_hiring_manager_cannot_add_skill(
        self, hiring_manager_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {"skill_name": "Blocked"}
        response = await hiring_manager_client.post(
            f"/candidates/{sample_candidate.id}/skills",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_hiring_manager_cannot_remove_skill(
        self,
        hiring_manager_client: AsyncClient,
        candidate_with_skill: Candidate,
        sample_skill: Skill,
    ):
        response = await hiring_manager_client.post(
            f"/candidates/{candidate_with_skill.id}/skills/{sample_skill.id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 403

    async def test_hiring_manager_cannot_create_candidate(
        self, hiring_manager_client: AsyncClient
    ):
        form_data = {
            "first_name": "Blocked",
            "last_name": "Create",
            "email": "blocked.create@example.com",
        }
        response = await hiring_manager_client.post(
            "/candidates/create", data=form_data, follow_redirects=False
        )
        assert response.status_code == 403

    async def test_hiring_manager_cannot_edit_candidate(
        self, hiring_manager_client: AsyncClient, sample_candidate: Candidate
    ):
        form_data = {
            "first_name": "Blocked",
            "last_name": "Edit",
            "email": "blocked.edit@example.com",
        }
        response = await hiring_manager_client.post(
            f"/candidates/{sample_candidate.id}/edit",
            data=form_data,
            follow_redirects=False,
        )
        assert response.status_code == 403


class TestCandidatePagination:
    async def test_pagination_first_page(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        for i in range(25):
            candidate = Candidate(
                first_name=f"Candidate{i}",
                last_name=f"Last{i}",
                email=f"candidate{i}@example.com",
            )
            db_session.add(candidate)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.get(
            "/candidates?page=1", follow_redirects=False
        )
        assert response.status_code == 200
        assert "Candidate" in response.text

    async def test_pagination_second_page(
        self, admin_client: AsyncClient, db_session: AsyncSession
    ):
        for i in range(25):
            candidate = Candidate(
                first_name=f"PageCandidate{i}",
                last_name=f"PageLast{i}",
                email=f"pagecandidate{i}@example.com",
            )
            db_session.add(candidate)
        await db_session.flush()
        await db_session.commit()

        response = await admin_client.get(
            "/candidates?page=2", follow_redirects=False
        )
        assert response.status_code == 200