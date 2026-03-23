import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.detection import Detection
from app.models.satellite_image import SatelliteImage
from app.models.user import User
from app.schemas.image import ImageCompare, ImageTileResponse
from app.storage import get_client
from app.config import settings

router = APIRouter(prefix="/images", tags=["images"])


def _stream_url(image_id: UUID) -> str:
    return f"/images/{image_id}/stream"


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
        before_url=_stream_url(before.id),
        after_url=_stream_url(after.id),
        before_captured_at=before.captured_at,
        after_captured_at=after.captured_at,
    )


@router.get("/{image_id}/stream")
async def stream_image(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SatelliteImage).where(SatelliteImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        response = get_client().get_object(settings.minio_bucket, image.storage_path)
        data = response.read()
        response.close()
        response.release_conn()
    except Exception:
        raise HTTPException(status_code=404, detail="Image file not found in storage")

    ext = image.storage_path.rsplit(".", 1)[-1].lower()
    content_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/tiff"

    return StreamingResponse(io.BytesIO(data), media_type=content_type)


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
    return {"url": _stream_url(image.id)}
