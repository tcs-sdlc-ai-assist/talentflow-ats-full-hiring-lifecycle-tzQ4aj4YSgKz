import logging
import math
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import (
    AuditLogCreate,
    AuditLogFilterParams,
    AuditLogListResponse,
    AuditLogResponse,
)

logger = logging.getLogger(__name__)


class AuditTrailService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        user_id: Optional[int],
        action: str,
        entity_type: str,
        entity_id: int,
        details: Optional[str] = None,
    ) -> AuditLog:
        try:
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
            self.db.add(audit_entry)
            await self.db.flush()
            await self.db.refresh(audit_entry)
            logger.info(
                "Audit log created: user_id=%s action=%s entity_type=%s entity_id=%s",
                user_id,
                action,
                entity_type,
                entity_id,
            )
            return audit_entry
        except Exception:
            logger.exception(
                "Failed to create audit log entry: user_id=%s action=%s entity_type=%s entity_id=%s",
                user_id,
                action,
                entity_type,
                entity_id,
            )
            raise

    async def query_logs(
        self,
        filters: Optional[AuditLogFilterParams] = None,
    ) -> AuditLogListResponse:
        if filters is None:
            filters = AuditLogFilterParams()

        page = filters.page
        per_page = filters.per_page

        count_query = select(func.count()).select_from(AuditLog)
        count_query = self._apply_filters(count_query, filters)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        total_pages = max(1, math.ceil(total / per_page)) if total > 0 else 0

        query = (
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        query = self._apply_filters(query, filters)

        result = await self.db.execute(query)
        audit_logs = result.scalars().all()

        items: list[AuditLogResponse] = []
        for log in audit_logs:
            username: Optional[str] = None
            if log.user is not None:
                username = log.user.username
            elif log.user_id is not None:
                user_result = await self.db.execute(
                    select(User.username).where(User.id == log.user_id)
                )
                user_row = user_result.scalar_one_or_none()
                if user_row is not None:
                    username = user_row

            items.append(
                AuditLogResponse(
                    id=log.id,
                    timestamp=log.timestamp,
                    user_id=log.user_id,
                    action=log.action,
                    entity_type=log.entity_type,
                    entity_id=log.entity_id,
                    details=log.details,
                    username=username,
                )
            )

        return AuditLogListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def get_recent_logs(self, limit: int = 10) -> list[AuditLogResponse]:
        query = (
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        audit_logs = result.scalars().all()

        items: list[AuditLogResponse] = []
        for log in audit_logs:
            username: Optional[str] = None
            if log.user is not None:
                username = log.user.username
            elif log.user_id is not None:
                user_result = await self.db.execute(
                    select(User.username).where(User.id == log.user_id)
                )
                user_row = user_result.scalar_one_or_none()
                if user_row is not None:
                    username = user_row

            items.append(
                AuditLogResponse(
                    id=log.id,
                    timestamp=log.timestamp,
                    user_id=log.user_id,
                    action=log.action,
                    entity_type=log.entity_type,
                    entity_id=log.entity_id,
                    details=log.details,
                    username=username,
                )
            )

        return items

    def _apply_filters(self, query, filters: AuditLogFilterParams):
        if filters.user_id is not None:
            query = query.where(AuditLog.user_id == filters.user_id)

        if filters.entity_type is not None:
            query = query.where(AuditLog.entity_type == filters.entity_type)

        if filters.entity_id is not None:
            query = query.where(AuditLog.entity_id == filters.entity_id)

        if filters.action is not None:
            query = query.where(AuditLog.action.ilike(f"%{filters.action}%"))

        if filters.date_from is not None:
            query = query.where(AuditLog.timestamp >= filters.date_from)

        if filters.date_to is not None:
            query = query.where(AuditLog.timestamp <= filters.date_to)

        return query