import logging
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

COOKIE_NAME = "session"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        logger.exception("Error verifying password")
        return False


def create_session_cookie(user_id: int) -> str:
    return _serializer.dumps({"user_id": user_id})


def verify_session_cookie(cookie_value: str) -> Optional[int]:
    try:
        data = _serializer.loads(cookie_value, max_age=SESSION_MAX_AGE)
        user_id = data.get("user_id")
        if user_id is None:
            logger.warning("Session cookie missing user_id")
            return None
        return int(user_id)
    except SignatureExpired:
        logger.info("Session cookie expired")
        return None
    except BadSignature:
        logger.warning("Session cookie has invalid signature")
        return None
    except Exception:
        logger.exception("Unexpected error verifying session cookie")
        return None