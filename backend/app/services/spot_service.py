from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from fastapi import HTTPException, status

from app.models.construction_spot import ConstructionSpot
from app.models.user import User
from app.services.audit_service import create_audit_log

ACTION_TO_STATUS = {
    "marked_legal": "legal",
    "marked_illegal": "illegal",
    "marked_resolved": "resolved",
    "re_approved": "legal",
    "re_flagged": "flagged",
}


async def review_spot(
    db: AsyncSession,
    spot_id: UUID,
    action: str,
    version: int,
    officer: User,
    notes: str | None = None,
) -> ConstructionSpot:
    new_status = ACTION_TO_STATUS.get(action)
    if not new_status:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    now = datetime.now(timezone.utc)
    values = {
        "status": new_status,
        "reviewed_by_id": officer.id,
        "reviewed_at": now,
        "notes": notes,
        "version": version + 1,
    }
    if new_status == "legal":
        values["grace_period_until"] = now + relativedelta(months=12)

    # Atomic update with version check — prevents TOCTOU race
    result = await db.execute(
        update(ConstructionSpot)
        .where(ConstructionSpot.id == spot_id, ConstructionSpot.version == version)
        .values(**values)
        .returning(ConstructionSpot)
    )
    spot = result.scalar_one_or_none()
    if not spot:
        # Check if spot exists at all
        exists = await db.execute(select(ConstructionSpot.id).where(ConstructionSpot.id == spot_id))
        if not exists.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Spot not found")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version conflict — spot was modified by another user",
        )

    await create_audit_log(db, officer_id=officer.id, spot_id=spot_id, action=action, notes=notes)
    await db.commit()
    await db.refresh(spot)
    return spot


async def get_spot_stats(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ConstructionSpot.status, func.count(ConstructionSpot.id))
        .group_by(ConstructionSpot.status)
    )
    stats = {row[0]: row[1] for row in result.all()}
    return stats
