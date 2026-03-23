"""
Seed a realistic demo detection in PCMC area (Pimpri-Chinchwad, Pune).
Shows one flagged construction spot on the map with full detection history.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://pcmc:pcmc_dev_password@db:5432/pcmc_geo"
)

# PCMC area — Akurdi industrial zone, known construction activity
# A realistic small plot (~50m x 40m)
SPOT_WKT = (
    "POLYGON(("
    "73.8312 18.6487,"
    "73.8317 18.6487,"
    "73.8317 18.6491,"
    "73.8312 18.6491,"
    "73.8312 18.6487"
    "))"
)

# Slightly larger bounds for the satellite image tiles
IMAGE_BOUNDS_WKT = (
    "POLYGON(("
    "73.820 18.640,"
    "73.845 18.640,"
    "73.845 18.660,"
    "73.820 18.660,"
    "73.820 18.640"
    "))"
)

NOW = datetime.now(timezone.utc)
THIRTY_DAYS_AGO = NOW - timedelta(days=30)
SEVEN_DAYS_AGO = NOW - timedelta(days=7)


async def main():
    engine = create_async_engine(DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # ── 1. Two satellite images (before & after) ──────────────────────
        img_before_id = uuid.uuid4()
        img_after_id = uuid.uuid4()

        await db.execute(text("""
            INSERT INTO satellite_images
                (id, captured_at, ingested_at, storage_path, cloud_cover_pct,
                 resolution_meters, bounds, is_usable, source)
            VALUES
                (:id, :captured_at, now(), :path, 3.2, 10.0,
                 ST_GeomFromText(:wkt, 4326), true, 'sentinel2')
        """), {
            "id": str(img_before_id),
            "captured_at": THIRTY_DAYS_AGO,
            "path": f"sentinel2/2026/02/akurdi_{img_before_id}.tif",
            "wkt": IMAGE_BOUNDS_WKT,
        })

        await db.execute(text("""
            INSERT INTO satellite_images
                (id, captured_at, ingested_at, storage_path, cloud_cover_pct,
                 resolution_meters, bounds, is_usable, source)
            VALUES
                (:id, :captured_at, now(), :path, 1.8, 10.0,
                 ST_GeomFromText(:wkt, 4326), true, 'sentinel2')
        """), {
            "id": str(img_after_id),
            "captured_at": SEVEN_DAYS_AGO,
            "path": f"sentinel2/2026/03/akurdi_{img_after_id}.tif",
            "wkt": IMAGE_BOUNDS_WKT,
        })

        # ── 2. Construction spot ──────────────────────────────────────────
        spot_id = uuid.uuid4()

        await db.execute(text("""
            INSERT INTO construction_spots
                (id, geometry, status, first_detected_at, last_detected_at,
                 grace_period_until, confidence_score, change_type, version)
            VALUES
                (:id, ST_GeomFromText(:wkt, 4326),
                 'flagged', :first, :last,
                 :grace, 0.91, 'foundation', 1)
        """), {
            "id": str(spot_id),
            "wkt": SPOT_WKT,
            "first": SEVEN_DAYS_AGO,
            "last": SEVEN_DAYS_AGO,
            "grace": NOW + timedelta(days=23),   # 30-day grace period from detection
        })

        # ── 3. Detection record ───────────────────────────────────────────
        detection_id = uuid.uuid4()

        await db.execute(text("""
            INSERT INTO detections
                (id, spot_id, detected_at, comparison_interval, confidence,
                 image_before_id, image_after_id, change_mask_path, area_sq_meters)
            VALUES
                (:id, :spot_id, :detected_at, '30d', 0.91,
                 :before_id, :after_id, :mask_path, 1980.0)
        """), {
            "id": str(detection_id),
            "spot_id": str(spot_id),
            "detected_at": SEVEN_DAYS_AGO,
            "before_id": str(img_before_id),
            "after_id": str(img_after_id),
            "mask_path": f"masks/{spot_id}/change_mask.png",
        })

        await db.commit()

    print("Demo detection seeded:")
    print(f"  Spot ID      : {spot_id}")
    print(f"  Location     : Akurdi, PCMC (18.6489°N, 73.8315°E)")
    print(f"  Status       : flagged")
    print(f"  Change type  : foundation")
    print(f"  Confidence   : 91%")
    print(f"  Area         : ~1980 m²")
    print(f"  Grace period : ends {(NOW + timedelta(days=23)).strftime('%Y-%m-%d')}")
    print()
    print("Open http://localhost:3000 and log in — the spot should appear on the map.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
