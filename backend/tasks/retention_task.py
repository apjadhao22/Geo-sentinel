import logging
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory as session_factory
from app.models.satellite_image import SatelliteImage
from app.storage import get_client

logger = logging.getLogger(__name__)


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
            except Exception as e:
                err_str = str(e)
                if "NoSuchKey" not in err_str and "does not exist" not in err_str.lower():
                    logger.warning("MinIO delete failed for %s: %s", image.storage_path, e)
                    continue  # skip DB delete to preserve consistency
            await db.delete(image)
            deleted_count += 1

        await db.commit()
        return {"deleted": deleted_count}
