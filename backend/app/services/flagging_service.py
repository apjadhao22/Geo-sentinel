from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from geoalchemy2.shape import to_shape, from_shape

from app.models.construction_spot import ConstructionSpot
from app.models.detection import Detection
from app.models.zone import Zone
from app.models.user import User


def compute_iou(geom_a, geom_b) -> float:
    intersection = geom_a.intersection(geom_b).area
    union = geom_a.union(geom_b).area
    return intersection / union if union > 0 else 0.0


async def process_detection(
    db: AsyncSession,
    detection_polygon,  # shapely Polygon
    confidence: float,
    comparison_interval: str,
    image_before_id: UUID,
    image_after_id: UUID,
    change_mask_path: str,
    area_sq_meters: float,
    change_type: str | None = None,
) -> ConstructionSpot | None:
    # Check overlap with existing active spots
    result = await db.execute(
        select(ConstructionSpot).where(
            ConstructionSpot.status.in_(["flagged", "illegal", "review_pending"])
        )
    )
    existing_spots = result.scalars().all()

    for spot in existing_spots:
        spot_geom = to_shape(spot.geometry)
        iou = compute_iou(detection_polygon, spot_geom)
        if iou > 0.5:
            # Merge into existing spot
            merged_geom = spot_geom.union(detection_polygon)
            spot.geometry = from_shape(merged_geom, srid=4326)
            spot.last_detected_at = datetime.now(timezone.utc)
            spot.confidence_score = max(spot.confidence_score, confidence)
            detection = Detection(
                spot_id=spot.id,
                detected_at=datetime.now(timezone.utc),
                comparison_interval=comparison_interval,
                confidence=confidence,
                image_before_id=image_before_id,
                image_after_id=image_after_id,
                change_mask_path=change_mask_path,
                area_sq_meters=area_sq_meters,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(spot, ["detections"])
            return spot

    # Check grace period (legal spots)
    legal_spots = await db.execute(
        select(ConstructionSpot).where(
            ConstructionSpot.status == "legal",
            ConstructionSpot.grace_period_until > datetime.now(timezone.utc),
        )
    )
    for spot in legal_spots.scalars().all():
        spot_geom = to_shape(spot.geometry)
        iou = compute_iou(detection_polygon, spot_geom)
        if iou > 0.5:
            return None  # In grace period, ignore

    # Check resolved spots — create new linked spot
    resolved_spots = await db.execute(
        select(ConstructionSpot).where(ConstructionSpot.status == "resolved")
    )
    previous_spot_id = None
    for spot in resolved_spots.scalars().all():
        spot_geom = to_shape(spot.geometry)
        iou = compute_iou(detection_polygon, spot_geom)
        if iou > 0.5:
            previous_spot_id = spot.id
            break

    # Auto-assign to zone reviewer
    assigned_to_id = await find_zone_reviewer(db, detection_polygon)

    # Create new spot
    now = datetime.now(timezone.utc)
    new_spot = ConstructionSpot(
        geometry=from_shape(detection_polygon, srid=4326),
        status="flagged",
        first_detected_at=now,
        last_detected_at=now,
        confidence_score=confidence,
        change_type=change_type,
        assigned_to_id=assigned_to_id,
        previous_spot_id=previous_spot_id,
        version=1,
    )
    db.add(new_spot)
    await db.flush()

    detection = Detection(
        spot_id=new_spot.id,
        detected_at=now,
        comparison_interval=comparison_interval,
        confidence=confidence,
        image_before_id=image_before_id,
        image_after_id=image_after_id,
        change_mask_path=change_mask_path,
        area_sq_meters=area_sq_meters,
    )
    db.add(detection)
    await db.commit()
    await db.refresh(new_spot, ["detections"])
    return new_spot


async def find_zone_reviewer(db: AsyncSession, polygon) -> UUID | None:
    centroid = polygon.centroid
    result = await db.execute(
        select(Zone)
        .options(selectinload(Zone.assigned_reviewer))
        .where(
            Zone.geometry.ST_Contains(
                f"SRID=4326;POINT({centroid.x} {centroid.y})"
            )
        )
    )
    zone = result.scalar_one_or_none()
    if zone and zone.assigned_reviewer:
        return zone.assigned_reviewer.id
    return None
