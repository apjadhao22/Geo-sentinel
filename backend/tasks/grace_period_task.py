from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.construction_spot import ConstructionSpot
from app.models.notification import Notification

engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def check_expired_grace_periods():
    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ConstructionSpot).where(
                ConstructionSpot.status == "legal",
                ConstructionSpot.grace_period_until <= now,
            )
        )
        expired_spots = result.scalars().all()

        for spot in expired_spots:
            spot.status = "review_pending"
            spot.review_prompted_at = now

            if spot.assigned_to_id:
                notification = Notification(
                    user_id=spot.assigned_to_id,
                    message=f"12-month review due for spot at ({spot.id}). Please re-evaluate.",
                )
                db.add(notification)

        await db.commit()
        return {"transitioned": len(expired_spots)}
