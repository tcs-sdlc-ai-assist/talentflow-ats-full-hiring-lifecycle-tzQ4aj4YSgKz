import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import async_session_factory, create_all_tables
from app.routers import applications, auth, candidates, dashboard, interviews, jobs, landing

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TalentFlow ATS...")

    await create_all_tables()
    logger.info("Database tables created/verified.")

    async with async_session_factory() as session:
        try:
            from app.services.auth_service import AuthService

            auth_service = AuthService(session)
            await auth_service.seed_default_admin()
            await session.commit()
            logger.info("Default admin seed completed.")
        except Exception:
            await session.rollback()
            logger.exception("Failed to seed default admin user.")

    yield

    logger.info("Shutting down TalentFlow ATS...")


app = FastAPI(
    title="TalentFlow ATS",
    description="Applicant Tracking System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(landing.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(interviews.router)
app.include_router(dashboard.router)