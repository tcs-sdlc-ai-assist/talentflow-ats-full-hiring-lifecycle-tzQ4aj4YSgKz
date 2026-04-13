import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_session_cookie, COOKIE_NAME
from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate, Skill, candidate_skills
from app.models.application import Application
from app.models.interview import Interview
from app.models.audit_log import AuditLog
from app.core.security import get_password_hash
from app.main import app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

test_async_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        username="testadmin",
        password_hash=get_password_hash("adminpass123"),
        full_name="Test Admin",
        role="Admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def recruiter_user(db_session: AsyncSession) -> User:
    user = User(
        username="testrecruiter",
        password_hash=get_password_hash("recruiterpass123"),
        full_name="Test Recruiter",
        role="Recruiter",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def hiring_manager_user(db_session: AsyncSession) -> User:
    user = User(
        username="testhiringmgr",
        password_hash=get_password_hash("hiringmgrpass123"),
        full_name="Test Hiring Manager",
        role="Hiring Manager",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def interviewer_user(db_session: AsyncSession) -> User:
    user = User(
        username="testinterviewer",
        password_hash=get_password_hash("interviewerpass123"),
        full_name="Test Interviewer",
        role="Interviewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    cookie_value = create_session_cookie(admin_user.id)
    client.cookies.set(COOKIE_NAME, cookie_value)
    yield client
    client.cookies.clear()


@pytest_asyncio.fixture
async def recruiter_client(client: AsyncClient, recruiter_user: User) -> AsyncClient:
    cookie_value = create_session_cookie(recruiter_user.id)
    client.cookies.set(COOKIE_NAME, cookie_value)
    yield client
    client.cookies.clear()


@pytest_asyncio.fixture
async def hiring_manager_client(client: AsyncClient, hiring_manager_user: User) -> AsyncClient:
    cookie_value = create_session_cookie(hiring_manager_user.id)
    client.cookies.set(COOKIE_NAME, cookie_value)
    yield client
    client.cookies.clear()


@pytest_asyncio.fixture
async def interviewer_client(client: AsyncClient, interviewer_user: User) -> AsyncClient:
    cookie_value = create_session_cookie(interviewer_user.id)
    client.cookies.set(COOKIE_NAME, cookie_value)
    yield client
    client.cookies.clear()


@pytest_asyncio.fixture
async def unauthenticated_client(client: AsyncClient) -> AsyncClient:
    client.cookies.clear()
    return client