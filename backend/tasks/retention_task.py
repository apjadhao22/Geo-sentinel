from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.satellite_image import SatelliteImage
from app.storage import get_client

engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def cleanup_old_images():
    async with session_factory() as db:
        cutoff = datetime.now(timezone.utc) - relativedelta(months=24)
        result = await db.execute(
            select(SatelliteImage).where(SatelliteImage.ingested_at < cutoff)
        )
        old_images = result.scalars().all()

        deleted_count = 0
        minio_client = get_client()
        for image in old_images:
            try:
                minio_client.remove_object(settings.minio_bucket, image.storage_path)
            except Exception:
                pass  # Object may already be deleted
            await db.delete(image)
            deleted_count += 1

        await db.commit()
        return {"deleted": deleted_count}
