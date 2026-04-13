from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, func

from app.core.database import Base


candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column("candidate_id", Integer, ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)

    from sqlalchemy.orm import relationship
    candidates = relationship(
        "Candidate",
        secondary=candidate_skills,
        back_populates="skills",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}')>"


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    email = Column(String(120), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    resume_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    from sqlalchemy.orm import relationship
    skills = relationship(
        "Skill",
        secondary=candidate_skills,
        back_populates="candidates",
        lazy="selectin",
    )

    applications = relationship(
        "Application",
        back_populates="candidate",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, email='{self.email}')>"