from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.audit_log import AuditLog


async def create_audit_log(
    db: AsyncSession,
    officer_id: UUID,
    spot_id: UUID,
    action: str,
    notes: str | None = None,
):
    log = AuditLog(officer_id=officer_id, spot_id=spot_id, action=action, notes=notes)
    db.add(log)


async def get_audit_logs(
    db: AsyncSession,
    officer_id: UUID | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if officer_id:
        query = query.where(AuditLog.officer_id == officer_id)
    if action:
        query = query.where(AuditLog.action == action)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


async def get_officer_summary(db: AsyncSession):
    result = await db.execute(
        select(
            AuditLog.officer_id,
            AuditLog.action,
            func.count(AuditLog.id).label("count"),
        )
        .group_by(AuditLog.officer_id, AuditLog.action)
    )
    return result.all()
