from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.construction_spot import ConstructionSpot
from app.models.detection import Detection
from app.models.user import User
from app.schemas.spot import SpotOut, SpotDetail, SpotReviewRequest, SpotAssignRequest, SpotStats, DetectionOut
from app.services.spot_service import review_spot, get_spot_stats
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/spots", tags=["spots"])


def _with_centroid(query):
    """Add ST_X/ST_Y centroid columns to a ConstructionSpot query."""
    centroid = func.ST_Centroid(ConstructionSpot.geometry)
    return query.add_columns(
        func.ST_Y(centroid).label("latitude"),
        func.ST_X(centroid).label("longitude"),
    )


def _build_spot_out(row) -> SpotOut:
    spot, lat, lng = row
    d = SpotOut.model_validate(spot)
    d.latitude = lat
    d.longitude = lng
    return d


@router.get("", response_model=list[SpotOut])
async def list_spots(
    status: Optional[str] = None,
    change_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_area: Optional[float] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(ConstructionSpot).order_by(ConstructionSpot.last_detected_at.desc())
    if status:
        query = query.where(ConstructionSpot.status == status)
    if change_type:
        query = query.where(ConstructionSpot.change_type == change_type)
    if date_from:
        query = query.where(ConstructionSpot.first_detected_at >= date_from)
    if date_to:
        query = query.where(ConstructionSpot.first_detected_at <= date_to)
    if min_area:
        query = query.join(Detection).where(Detection.area_sq_meters >= min_area).distinct()
    query = _with_centroid(query).limit(limit).offset(offset)
    result = await db.execute(query)
    return [_build_spot_out(row) for row in result.all()]


@router.get("/stats", response_model=SpotStats)
async def stats(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    raw = await get_spot_stats(db)
    return SpotStats(**raw)


@router.get("/review-pending", response_model=list[SpotOut])
async def review_pending(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = _with_centroid(
        select(ConstructionSpot).where(ConstructionSpot.status == "review_pending")
    )
    result = await db.execute(query)
    return [_build_spot_out(row) for row in result.all()]


async def _get_spot_with_coords(db: AsyncSession, spot_id: UUID) -> SpotDetail:
    query = _with_centroid(select(ConstructionSpot).where(ConstructionSpot.id == spot_id))
    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Spot not found")
    spot, lat, lng = row
    d = SpotDetail.model_validate(spot)
    d.latitude = lat
    d.longitude = lng
    return d


@router.get("/{spot_id}", response_model=SpotDetail)
async def get_spot(spot_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await _get_spot_with_coords(db, spot_id)


@router.patch("/{spot_id}/review", response_model=SpotDetail)
async def review(
    spot_id: UUID,
    body: SpotReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await review_spot(db, spot_id, body.action, body.version, user, body.notes)
    return await _get_spot_with_coords(db, spot_id)


@router.patch("/{spot_id}/assign", response_model=SpotDetail)
async def assign_spot(
    spot_id: UUID,
    body: SpotAssignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "super_admin")),
):
    result = await db.execute(select(ConstructionSpot).where(ConstructionSpot.id == spot_id))
    spot = result.scalar_one_or_none()
    if not spot:
        raise HTTPException(status_code=404, detail="Spot not found")
    spot.assigned_to_id = body.assigned_to_id
    await db.commit()
    return await _get_spot_with_coords(db, spot_id)


@router.get("/{spot_id}/detections", response_model=list[DetectionOut])
async def list_detections(
    spot_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Detection)
        .where(Detection.spot_id == spot_id)
        .order_by(Detection.detected_at.desc())
    )
    return result.scalars().all()
