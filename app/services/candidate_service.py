import logging
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate, Skill, candidate_skills
from app.schemas.candidate import CandidateCreate, CandidateUpdate

logger = logging.getLogger(__name__)


class CandidateService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_candidate(self, data: CandidateCreate) -> Candidate:
        existing = await self.db.execute(
            select(Candidate).where(Candidate.email == data.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"A candidate with email '{data.email}' already exists.")

        candidate = Candidate(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            linkedin_url=data.linkedin_url,
            resume_text=data.resume_text,
        )
        self.db.add(candidate)
        await self.db.flush()

        if data.skills:
            for skill_name in data.skills:
                skill = await self._get_or_create_skill(skill_name)
                candidate.skills.append(skill)
            await self.db.flush()

        await self.db.refresh(candidate)
        return candidate

    async def update_candidate(self, candidate_id: int, data: CandidateUpdate) -> Candidate:
        candidate = await self._get_candidate_or_raise(candidate_id)

        if data.first_name is not None:
            candidate.first_name = data.first_name
        if data.last_name is not None:
            candidate.last_name = data.last_name
        if data.email is not None:
            if data.email != candidate.email:
                existing = await self.db.execute(
                    select(Candidate).where(
                        Candidate.email == data.email,
                        Candidate.id != candidate_id,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    raise ValueError(f"A candidate with email '{data.email}' already exists.")
            candidate.email = data.email
        if data.phone is not None:
            candidate.phone = data.phone
        if data.linkedin_url is not None:
            candidate.linkedin_url = data.linkedin_url
        if data.resume_text is not None:
            candidate.resume_text = data.resume_text

        if data.skills is not None:
            candidate.skills.clear()
            for skill_name in data.skills:
                skill = await self._get_or_create_skill(skill_name)
                candidate.skills.append(skill)

        await self.db.flush()
        await self.db.refresh(candidate)
        return candidate

    async def get_candidate_by_id(self, candidate_id: int) -> Optional[Candidate]:
        result = await self.db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.skills),
                selectinload(Candidate.applications),
            )
        )
        return result.scalar_one_or_none()

    async def list_candidates(
        self,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Candidate], int]:
        query = select(Candidate).options(
            selectinload(Candidate.skills),
            selectinload(Candidate.applications),
        )
        count_query = select(func.count()).select_from(Candidate)

        if search:
            search_term = f"%{search}%"
            skill_subquery = (
                select(candidate_skills.c.candidate_id)
                .join(Skill, Skill.id == candidate_skills.c.skill_id)
                .where(Skill.name.ilike(search_term))
            )
            search_filter = or_(
                Candidate.first_name.ilike(search_term),
                Candidate.last_name.ilike(search_term),
                Candidate.email.ilike(search_term),
                Candidate.id.in_(skill_subquery),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Candidate.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        candidates = list(result.scalars().unique().all())

        return candidates, total

    async def add_skill(self, candidate_id: int, skill_name: str) -> Candidate:
        candidate = await self._get_candidate_or_raise(candidate_id)

        skill_name = skill_name.strip()
        if not skill_name:
            raise ValueError("Skill name must not be empty.")
        if len(skill_name) > 50:
            raise ValueError("Skill name must be at most 50 characters.")

        skill = await self._get_or_create_skill(skill_name)

        existing_skill_ids = {s.id for s in candidate.skills}
        if skill.id not in existing_skill_ids:
            candidate.skills.append(skill)
            await self.db.flush()

        await self.db.refresh(candidate)
        return candidate

    async def remove_skill(self, candidate_id: int, skill_id: int) -> Candidate:
        candidate = await self._get_candidate_or_raise(candidate_id)

        skill_to_remove = None
        for skill in candidate.skills:
            if skill.id == skill_id:
                skill_to_remove = skill
                break

        if skill_to_remove is None:
            raise ValueError(f"Skill with id {skill_id} is not associated with this candidate.")

        candidate.skills.remove(skill_to_remove)
        await self.db.flush()
        await self.db.refresh(candidate)
        return candidate

    async def _get_candidate_or_raise(self, candidate_id: int) -> Candidate:
        result = await self.db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.skills),
                selectinload(Candidate.applications),
            )
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            raise ValueError(f"Candidate with id {candidate_id} not found.")
        return candidate

    async def _get_or_create_skill(self, skill_name: str) -> Skill:
        skill_name = skill_name.strip()
        result = await self.db.execute(
            select(Skill).where(func.lower(Skill.name) == func.lower(skill_name))
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            skill = Skill(name=skill_name)
            self.db.add(skill)
            await self.db.flush()
            await self.db.refresh(skill)
        return skill