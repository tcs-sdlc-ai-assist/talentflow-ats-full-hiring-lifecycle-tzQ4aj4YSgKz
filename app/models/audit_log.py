from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(500), nullable=False)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False)
    details = Column(Text, nullable=True)

    user = relationship("User", back_populates="audit_logs", lazy="selectin")