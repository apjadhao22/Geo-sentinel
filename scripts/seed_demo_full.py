"""
Full demo seed: 10 construction spots across PCMC with synthetic
before/after satellite images uploaded to MinIO.

Run inside backend container:
    python seed_demo_full.py
"""
import asyncio
import io
import os
import uuid
from datetime import datetime, timezone, timedelta

import numpy as np
from PIL import Image as PILImage
from minio import Minio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://pcmc:pcmc_dev_password@db:5432/pcmc_geo"
)
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.environ.get("MINIO_ACCESS_KEY", "pcmc_minio")
MINIO_SECRET = os.environ.get("MINIO_SECRET_KEY", "pcmc_minio_secret")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "geo-sentinel")

NOW = datetime.now(timezone.utc)

# ── 10 real PCMC locations ─────────────────────────────────────────────────
SPOTS = [
    # (name, lat, lon, status, change_type, confidence, area_m2, days_ago)
    ("Akurdi Industrial",    18.6489, 73.8315, "flagged",        "foundation",    0.91, 1980, 7),
    ("Nigdi Sector 27",      18.6583, 73.7718, "flagged",        "new_structure",  0.87, 3200, 5),
    ("Wakad Phase 2",        18.5985, 73.7620, "illegal",        "extension",      0.93, 2750, 14),
    ("Pimpri Gaon",          18.6270, 73.8032, "flagged",        "excavation",     0.78, 1450, 3),
    ("Chinchwad East",       18.6143, 73.7983, "review_pending", "new_structure",  0.85, 5100, 20),
    ("Bhosari MIDC",         18.6444, 73.8423, "flagged",        "land_clearing",  0.89, 8800, 2),
    ("Hinjewadi IT Park",    18.5914, 73.7214, "illegal",        "new_structure",  0.96, 6400, 30),
    ("Dehu Road Camp",       18.7078, 73.7583, "flagged",        "foundation",     0.82, 2200, 6),
    ("Chakan MIDC",          18.7624, 73.8600, "flagged",        "excavation",     0.74, 3900, 4),
    ("Ravet Junction",       18.6450, 73.7390, "review_pending", "extension",      0.88, 1700, 10),
]

# Small polygon offset so each spot has a distinct shape (±~50m)
POLY_DELTA = 0.0005


def spot_polygon(lat: float, lon: float) -> str:
    d = POLY_DELTA
    return (
        f"POLYGON(("
        f"{lon} {lat},"
        f"{lon+d} {lat},"
        f"{lon+d} {lat+d},"
        f"{lon} {lat+d},"
        f"{lon} {lat}"
        f"))"
    )


def image_bounds(lat: float, lon: float) -> str:
    m = 0.02
    return (
        f"POLYGON(("
        f"{lon-m} {lat-m},"
        f"{lon+m} {lat-m},"
        f"{lon+m} {lat+m},"
        f"{lon-m} {lat+m},"
        f"{lon-m} {lat-m}"
        f"))"
    )


# ── Synthetic image generation ─────────────────────────────────────────────

def _noise(shape, scale=20):
    return (np.random.rand(*shape) * scale).astype(np.uint8)


def make_before_image(size=256) -> bytes:
    """Green/vegetation patch — undeveloped land."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    # Base green (vegetation)
    img[:, :, 0] = 60 + _noise((size, size), 30)
    img[:, :, 1] = 110 + _noise((size, size), 40)
    img[:, :, 2] = 50 + _noise((size, size), 20)
    # Brown earth patches
    for _ in range(6):
        x, y = np.random.randint(20, size - 40, 2)
        w, h = np.random.randint(20, 40, 2)
        x2, y2 = min(x + w, size), min(y + h, size)
        aw, ah = x2 - x, y2 - y
        img[y:y2, x:x2, 0] = 130 + _noise((ah, aw), 25)
        img[y:y2, x:x2, 1] = 100 + _noise((ah, aw), 20)
        img[y:y2, x:x2, 2] = 60 + _noise((ah, aw), 15)
    pil = PILImage.fromarray(img, "RGB")
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def make_after_image(size=256) -> bytes:
    """Grey concrete construction site — disturbed earth, structures."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    # Base disturbed earth
    img[:, :, 0] = 140 + _noise((size, size), 30)
    img[:, :, 1] = 120 + _noise((size, size), 25)
    img[:, :, 2] = 100 + _noise((size, size), 20)
    # Concrete slabs / foundation blocks
    for _ in range(4):
        x, y = np.random.randint(10, size - 60, 2)
        w, h = np.random.randint(30, 60, 2)
        x2, y2 = min(x + w, size), min(y + h, size)
        aw, ah = x2 - x, y2 - y
        shade = 180 + np.random.randint(0, 30)
        img[y:y2, x:x2, :] = shade + _noise((ah, aw, 3), 15)
    # Construction debris — dark patches
    for _ in range(5):
        x, y = np.random.randint(0, size - 20, 2)
        w, h = np.random.randint(8, 20, 2)
        x2, y2 = min(x + w, size), min(y + h, size)
        aw, ah = x2 - x, y2 - y
        img[y:y2, x:x2, :] = 60 + _noise((ah, aw, 3), 20)
    # Red/orange boundary markers
    img[size//2-2:size//2+2, :, 0] = 220
    img[size//2-2:size//2+2, :, 1] = 80
    img[size//2-2:size//2+2, :, 2] = 60
    pil = PILImage.fromarray(img, "RGB")
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ── MinIO upload ───────────────────────────────────────────────────────────

def ensure_bucket(client: Minio):
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


def upload_bytes(client: Minio, object_name: str, data: bytes, content_type: str = "image/jpeg"):
    client.put_object(
        MINIO_BUCKET, object_name,
        io.BytesIO(data), len(data),
        content_type=content_type,
    )


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    np.random.seed(42)

    minio = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    ensure_bucket(minio)

    engine = create_async_engine(DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Clear previous demo data (images, detections, spots)
    async with Session() as db:
        await db.execute(text("DELETE FROM detections"))
        await db.execute(text("DELETE FROM construction_spots"))
        await db.execute(text("DELETE FROM satellite_images"))
        await db.commit()
    print("Cleared previous demo data.")

    async with Session() as db:
        for i, (name, lat, lon, status, change_type, confidence, area, days_ago) in enumerate(SPOTS):
            detected_at = NOW - timedelta(days=days_ago)
            before_at = NOW - timedelta(days=days_ago + 30)

            # Generate and upload images
            before_bytes = make_before_image()
            after_bytes = make_after_image()
            before_path = f"sentinel2/before/{uuid.uuid4()}.jpg"
            after_path = f"sentinel2/after/{uuid.uuid4()}.jpg"
            upload_bytes(minio, before_path, before_bytes)
            upload_bytes(minio, after_path, after_bytes)

            # Satellite image records
            img_before_id = uuid.uuid4()
            img_after_id = uuid.uuid4()
            bounds_wkt = image_bounds(lat, lon)

            await db.execute(text("""
                INSERT INTO satellite_images
                    (id, captured_at, ingested_at, storage_path, cloud_cover_pct,
                     resolution_meters, bounds, is_usable, source)
                VALUES (:id, :cap, now(), :path, :cloud, 10.0,
                        ST_GeomFromText(:wkt, 4326), true, 'sentinel2')
            """), {"id": str(img_before_id), "cap": before_at, "path": before_path,
                   "cloud": round(np.random.uniform(1, 8), 1), "wkt": bounds_wkt})

            await db.execute(text("""
                INSERT INTO satellite_images
                    (id, captured_at, ingested_at, storage_path, cloud_cover_pct,
                     resolution_meters, bounds, is_usable, source)
                VALUES (:id, :cap, now(), :path, :cloud, 10.0,
                        ST_GeomFromText(:wkt, 4326), true, 'sentinel2')
            """), {"id": str(img_after_id), "cap": detected_at, "path": after_path,
                   "cloud": round(np.random.uniform(1, 5), 1), "wkt": bounds_wkt})

            # Construction spot
            spot_id = uuid.uuid4()
            grace_until = (detected_at + timedelta(days=30)) if status == "flagged" else None

            await db.execute(text("""
                INSERT INTO construction_spots
                    (id, geometry, status, first_detected_at, last_detected_at,
                     grace_period_until, confidence_score, change_type, version)
                VALUES (:id, ST_GeomFromText(:wkt, 4326),
                        :status, :first, :last, :grace, :conf, :ct, 1)
            """), {
                "id": str(spot_id),
                "wkt": spot_polygon(lat, lon),
                "status": status,
                "first": detected_at,
                "last": detected_at,
                "grace": grace_until,
                "conf": confidence,
                "ct": change_type,
            })

            # Detection record
            await db.execute(text("""
                INSERT INTO detections
                    (id, spot_id, detected_at, comparison_interval, confidence,
                     image_before_id, image_after_id, change_mask_path, area_sq_meters)
                VALUES (:id, :spot_id, :det_at, '30d', :conf,
                        :before_id, :after_id, :mask, :area)
            """), {
                "id": str(uuid.uuid4()),
                "spot_id": str(spot_id),
                "det_at": detected_at,
                "conf": confidence,
                "before_id": str(img_before_id),
                "after_id": str(img_after_id),
                "mask": f"masks/{spot_id}/change_mask.png",
                "area": float(area),
            })

            print(f"  [{i+1:2d}/10] {name:25s} {status:15s} {change_type}")

        await db.commit()

    await engine.dispose()
    print("\nDone! 10 spots seeded with before/after images in MinIO.")
    print("Refresh http://localhost:3000 to see all markers.")


if __name__ == "__main__":
    asyncio.run(main())
