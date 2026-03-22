from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.services.notification_service import get_notifications, get_unread_count, mark_read
from app.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_notifications(db, user.id, unread_only)


@router.get("/count")
async def unread_count(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    count = await get_unread_count(db, user.id)
    return {"unread": count}


@router.patch("/{notification_id}/read")
async def read_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await mark_read(db, notification_id, user.id)
    return {"status": "ok"}
