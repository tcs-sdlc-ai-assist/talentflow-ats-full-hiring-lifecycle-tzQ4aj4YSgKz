import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    full_name = Column(String(64), nullable=False)
    role = Column(String(32), nullable=False, default="Interviewer", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    jobs = relationship("Job", back_populates="hiring_manager", lazy="selectin")
    interviews = relationship(
        "InterviewAssignment", back_populates="interviewer", lazy="selectin"
    )
    audit_logs = relationship("AuditLog", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"