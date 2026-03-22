from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.services.audit_service import get_audit_logs, get_officer_summary
from app.dependencies import require_role
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogOut])
async def audit_logs(
    officer_id: Optional[UUID] = None,
    action: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("super_admin")),
):
    return await get_audit_logs(
        db,
        officer_id=officer_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/officer-summary")
async def officer_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("super_admin")),
):
    return await get_officer_summary(db)
