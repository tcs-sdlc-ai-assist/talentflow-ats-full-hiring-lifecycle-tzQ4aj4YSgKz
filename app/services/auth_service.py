import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, username: str, password: str) -> Optional[User]:
        """Authenticate user by username and password.

        Returns the User object if credentials are valid and user is active,
        otherwise returns None.
        """
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if user is None:
            logger.info("Login failed: user '%s' not found", username)
            return None

        if not verify_password(password, user.password_hash):
            logger.info("Login failed: invalid password for user '%s'", username)
            return None

        if not user.is_active:
            logger.info("Login failed: user '%s' is inactive", username)
            return None

        logger.info("Login successful for user '%s' (id=%d, role=%s)", user.username, user.id, user.role)
        return user

    async def register(
        self,
        username: str,
        password: str,
        full_name: str,
        role: str = "Interviewer",
    ) -> Optional[User]:
        """Register a new user with hashed password.

        Default role is 'Interviewer'. Returns the created User object,
        or None if the username already exists.
        """
        existing_stmt = select(User).where(User.username == username)
        result = await self.db.execute(existing_stmt)
        existing_user = result.scalars().first()

        if existing_user is not None:
            logger.warning("Registration failed: username '%s' already exists", username)
            return None

        hashed_password = get_password_hash(password)

        new_user = User(
            username=username,
            password_hash=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
        )

        self.db.add(new_user)
        await self.db.flush()
        await self.db.refresh(new_user)

        logger.info(
            "User registered: '%s' (id=%d, role=%s)",
            new_user.username,
            new_user.id,
            new_user.role,
        )
        return new_user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Retrieve a user by their ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Retrieve a user by their username."""
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def seed_default_admin(self) -> None:
        """Create the default admin user on startup if it does not already exist.

        Uses DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD from settings.
        """
        admin_username = settings.DEFAULT_ADMIN_USERNAME
        admin_password = settings.DEFAULT_ADMIN_PASSWORD

        existing_stmt = select(User).where(User.username == admin_username)
        result = await self.db.execute(existing_stmt)
        existing_admin = result.scalars().first()

        if existing_admin is not None:
            logger.info("Default admin user '%s' already exists, skipping seed", admin_username)
            return

        hashed_password = get_password_hash(admin_password)

        admin_user = User(
            username=admin_username,
            password_hash=hashed_password,
            full_name="System Administrator",
            role="Admin",
            is_active=True,
        )

        self.db.add(admin_user)
        await self.db.flush()
        await self.db.refresh(admin_user)

        logger.info(
            "Default admin user created: '%s' (id=%d, role=%s)",
            admin_user.username,
            admin_user.id,
            admin_user.role,
        )