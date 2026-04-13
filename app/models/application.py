from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="Applied", index=True)
    applied_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    job = relationship("Job", back_populates="applications", lazy="selectin")
    candidate = relationship("Candidate", back_populates="applications", lazy="selectin")
    interviews = relationship(
        "Interview",
        back_populates="application",
        lazy="selectin",
        cascade="all, delete-orphan",
    )