from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.detection import Detection
from app.models.satellite_image import SatelliteImage
from app.models.user import User
from app.schemas.image import ImageCompare, ImageTileResponse
from app.storage import get_presigned_url

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/compare", response_model=ImageCompare)
async def compare_images(
    detection_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")

    before = await db.get(SatelliteImage, detection.image_before_id)
    after = await db.get(SatelliteImage, detection.image_after_id)
    if not before or not after:
        raise HTTPException(status_code=404, detail="Referenced satellite image not found")

    return ImageCompare(
        before_url=get_presigned_url(before.storage_path),
        after_url=get_presigned_url(after.storage_path),
        before_captured_at=before.captured_at,
        after_captured_at=after.captured_at,
    )


@router.get("/{image_id}/tile", response_model=ImageTileResponse)
async def get_image_tile(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SatelliteImage).where(SatelliteImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    url = get_presigned_url(image.storage_path)
    return {"url": url}
