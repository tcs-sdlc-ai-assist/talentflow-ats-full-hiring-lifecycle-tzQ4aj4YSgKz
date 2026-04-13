from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    interviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False)
    feedback_rating = Column(Integer, nullable=True)
    feedback_notes = Column(Text, nullable=True)
    feedback_submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    application = relationship("Application", back_populates="interviews", lazy="selectin")
    interviewer = relationship("User", back_populates="interviews", lazy="selectin")