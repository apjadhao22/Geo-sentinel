from __future__ import annotations
import os
import tempfile
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon, mapping
from shapely.wkt import loads as wkt_loads

from app.models.satellite_image import SatelliteImage
from app.models.detection import Detection
from app.models.spot import Spot
from app.storage import download_image, get_presigned_url
from ml.inference import run_inference
from ml.postprocessing import (
    threshold_mask,
    apply_morphology,
    extract_regions,
    filter_by_area,
    INTERVAL_THRESHOLDS,
    SENTINEL2_RESOLUTION,
)
from ml.classifier import classify_change
from rasterio.transform import xy as rasterio_xy

logger = logging.getLogger(__name__)

INTERVALS = list(INTERVAL_THRESHOLDS.keys())  # ["1d", "7d", "15d", "30d"]


def _pixel_polygon_to_geo(pixel_polygon: list, transform) -> list:
    """Convert [[col, row], ...] pixel coords to [[lon, lat], ...] geographic coords."""
    return [
        list(rasterio_xy(transform, row, col))  # returns (x, y) = (lon, lat)
        for col, row in pixel_polygon
    ]


async def _find_image_for_interval(
    db: AsyncSession,
    current_image: SatelliteImage,
    interval: str,
) -> SatelliteImage | None:
    """Find the most recent image captured before the interval window."""
    days = {"1d": 1, "7d": 7, "15d": 15, "30d": 30}[interval]
    from datetime import timedelta
    cutoff = current_image.captured_at - timedelta(days=days)
    result = await db.execute(
        select(SatelliteImage)
        .where(SatelliteImage.captured_at <= cutoff)
        .order_by(SatelliteImage.captured_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _merge_or_create_spot(
    db: AsyncSession,
    polygon: Polygon,
    area_sq_meters: float,
    classification: str,
    detection: Detection,
) -> Spot:
    """Find existing spot with >50% IoU overlap, or create new one."""
    from sqlalchemy import text

    # Use ST_AsText to avoid GeoAlchemy2 type coercion issues with raw text() queries
    result = await db.execute(
        text("""
            SELECT id, ST_AsText(geom)
            FROM spots
            WHERE ST_Intersects(geom, ST_GeomFromText(:wkt, 4326))
            ORDER BY ST_Area(ST_Intersection(geom, ST_GeomFromText(:wkt, 4326))) DESC
            LIMIT 1
        """),
        {"wkt": polygon.wkt},
    )
    row = result.fetchone()

    if row:
        existing_geom = wkt_loads(row[1])
        intersection_area = existing_geom.intersection(polygon).area
        union_area = existing_geom.union(polygon).area
        iou = intersection_area / union_area if union_area > 0 else 0.0
        if iou > 0.5:
            spot = await db.get(Spot, row[0])
            detection.spot_id = spot.id
            return spot

    # Create new spot
    spot = Spot(
        id=uuid4(),
        geom=from_shape(polygon, srid=4326),
        status="flagged",
        classification=classification,
        area_sq_meters=area_sq_meters,
        first_detected_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(spot)
    detection.spot_id = spot.id
    return spot


async def run_pipeline(
    db: AsyncSession,
    current_image_id: str,
) -> dict:
    """Run the full ML detection pipeline for all 4 time intervals.

    For each interval:
    1. Find the 'before' image from the DB
    2. Download both images to temp files
    3. Run inference → change probability mask + affine transform
    4. Postprocess → binary mask → regions → filter by area
    5. Convert pixel polygons to geographic coordinates
    6. Classify each region
    7. Merge with existing spots (IoU) or create new spot
    8. Persist Detection records

    Returns summary dict with counts per interval.
    """
    current_image = await db.get(SatelliteImage, current_image_id)
    if not current_image:
        return {"status": "error", "message": f"Image {current_image_id} not found"}

    summary = {"status": "success", "intervals": {}}

    for interval in INTERVALS:
        before_image = await _find_image_for_interval(db, current_image, interval)
        if not before_image:
            logger.info("No before image found for interval %s", interval)
            summary["intervals"][interval] = {"status": "no_before_image", "detections": 0}
            continue

        with (
            tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as before_tmp,
            tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as after_tmp,
        ):
            before_path = before_tmp.name
            after_path = after_tmp.name

        try:
            download_image(before_image.storage_path, before_path)
            download_image(current_image.storage_path, after_path)

            prob_mask, transform = run_inference(before_path, after_path)
            binary_mask = threshold_mask(prob_mask, interval)
            binary_mask = apply_morphology(binary_mask)
            regions = extract_regions(binary_mask)
            regions = filter_by_area(regions, resolution_meters=SENTINEL2_RESOLUTION)

            detections_created = 0
            async with db.begin_nested() as savepoint:
                for region in regions:
                    geo_coords = _pixel_polygon_to_geo(region["polygon"], transform)
                    polygon = Polygon(geo_coords)
                    if not polygon.is_valid:
                        polygon = polygon.buffer(0)

                    classification = classify_change(
                        region["polygon"],
                        region["area_sq_meters"],
                    )

                    detection = Detection(
                        id=uuid4(),
                        image_before_id=before_image.id,
                        image_after_id=current_image.id,
                        interval=interval,
                        confidence=float(prob_mask[
                            int(region["centroid"][0]),
                            int(region["centroid"][1]),
                        ]),
                        geom=from_shape(polygon, srid=4326),
                        classification=classification,
                        detected_at=datetime.now(timezone.utc),
                    )
                    db.add(detection)

                    await _merge_or_create_spot(db, polygon, region["area_sq_meters"], classification, detection)
                    detections_created += 1

            summary["intervals"][interval] = {
                "status": "success",
                "detections": detections_created,
            }

        except Exception as e:
            logger.exception("Pipeline failed for interval %s: %s", interval, e)
            summary["intervals"][interval] = {"status": "error", "message": str(e)}

        finally:
            for p in (before_path, after_path):
                if os.path.exists(p):
                    os.unlink(p)

    await db.commit()
    return summary
