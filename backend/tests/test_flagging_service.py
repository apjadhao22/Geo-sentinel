import pytest
from datetime import datetime, timezone, timedelta
from shapely.geometry import box
from geoalchemy2.shape import from_shape
from app.models import ConstructionSpot, SatelliteImage
from app.services.flagging_service import process_detection, compute_iou


def test_compute_iou_identical():
    a = box(0, 0, 10, 10)
    b = box(0, 0, 10, 10)
    assert compute_iou(a, b) == 1.0


def test_compute_iou_no_overlap():
    a = box(0, 0, 10, 10)
    b = box(20, 20, 30, 30)
    assert compute_iou(a, b) == 0.0


def test_compute_iou_partial_overlap():
    a = box(0, 0, 10, 10)
    b = box(5, 0, 15, 10)
    iou = compute_iou(a, b)
    assert 0.3 < iou < 0.4  # 50/150 ≈ 0.333


@pytest.mark.asyncio
async def test_new_detection_creates_flagged_spot(db_session):
    now = datetime.now(timezone.utc)
    img_before = SatelliteImage(
        captured_at=now - timedelta(days=1),
        storage_path="test/before.tif",
        cloud_cover_pct=5.0,
        resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True,
        source="sentinel2",
    )
    img_after = SatelliteImage(
        captured_at=now,
        storage_path="test/after.tif",
        cloud_cover_pct=5.0,
        resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True,
        source="sentinel2",
    )
    db_session.add_all([img_before, img_after])
    await db_session.flush()

    polygon = box(73.795, 18.625, 73.798, 18.628)
    spot = await process_detection(
        db=db_session,
        detection_polygon=polygon,
        confidence=0.8,
        comparison_interval="7d",
        image_before_id=img_before.id,
        image_after_id=img_after.id,
        change_mask_path="masks/test.png",
        area_sq_meters=120.0,
        change_type="foundation",
    )
    assert spot is not None
    assert spot.status == "flagged"
    assert spot.confidence_score == 0.8
    assert len(spot.detections) == 1


@pytest.mark.asyncio
async def test_overlapping_detection_merges_into_existing(db_session):
    now = datetime.now(timezone.utc)
    img = SatelliteImage(
        captured_at=now,
        storage_path="test/img.tif",
        cloud_cover_pct=5.0,
        resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True,
        source="sentinel2",
    )
    db_session.add(img)
    await db_session.flush()

    poly1 = box(73.795, 18.625, 73.798, 18.628)
    spot1 = await process_detection(
        db=db_session,
        detection_polygon=poly1,
        confidence=0.7,
        comparison_interval="7d",
        image_before_id=img.id,
        image_after_id=img.id,
        change_mask_path="masks/1.png",
        area_sq_meters=100.0,
    )

    poly2 = box(73.7955, 18.6255, 73.7985, 18.6285)
    spot2 = await process_detection(
        db=db_session,
        detection_polygon=poly2,
        confidence=0.85,
        comparison_interval="15d",
        image_before_id=img.id,
        image_after_id=img.id,
        change_mask_path="masks/2.png",
        area_sq_meters=110.0,
    )

    assert spot2.id == spot1.id  # Same spot
    assert spot2.confidence_score == 0.85  # Updated to max


@pytest.mark.asyncio
async def test_detection_in_grace_period_is_ignored(db_session):
    now = datetime.now(timezone.utc)
    img = SatelliteImage(
        captured_at=now,
        storage_path="test/img2.tif",
        cloud_cover_pct=5.0,
        resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True,
        source="sentinel2",
    )
    db_session.add(img)
    await db_session.flush()

    legal_spot = ConstructionSpot(
        geometry=from_shape(box(73.795, 18.625, 73.798, 18.628), srid=4326),
        status="legal",
        first_detected_at=now - timedelta(days=30),
        last_detected_at=now - timedelta(days=30),
        confidence_score=0.8,
        grace_period_until=now + timedelta(days=300),
        version=2,
    )
    db_session.add(legal_spot)
    await db_session.flush()

    poly = box(73.7955, 18.6255, 73.7975, 18.6275)
    result = await process_detection(
        db=db_session,
        detection_polygon=poly,
        confidence=0.9,
        comparison_interval="7d",
        image_before_id=img.id,
        image_after_id=img.id,
        change_mask_path="masks/grace.png",
        area_sq_meters=80.0,
    )
    assert result is None  # Ignored


@pytest.mark.asyncio
async def test_detection_at_resolved_spot_creates_new_linked_spot(db_session):
    now = datetime.now(timezone.utc)
    img = SatelliteImage(
        captured_at=now,
        storage_path="test/img3.tif",
        cloud_cover_pct=5.0,
        resolution_meters=10.0,
        bounds="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        is_usable=True,
        source="sentinel2",
    )
    db_session.add(img)
    await db_session.flush()

    resolved_spot = ConstructionSpot(
        geometry=from_shape(box(73.795, 18.625, 73.798, 18.628), srid=4326),
        status="resolved",
        first_detected_at=now - timedelta(days=60),
        last_detected_at=now - timedelta(days=30),
        confidence_score=0.8,
        version=3,
    )
    db_session.add(resolved_spot)
    await db_session.flush()

    poly = box(73.7955, 18.6255, 73.7975, 18.6275)
    new_spot = await process_detection(
        db=db_session,
        detection_polygon=poly,
        confidence=0.75,
        comparison_interval="30d",
        image_before_id=img.id,
        image_after_id=img.id,
        change_mask_path="masks/new.png",
        area_sq_meters=90.0,
    )
    assert new_spot is not None
    assert new_spot.id != resolved_spot.id  # New spot created
    assert new_spot.previous_spot_id == resolved_spot.id  # Linked to old
    assert new_spot.status == "flagged"
