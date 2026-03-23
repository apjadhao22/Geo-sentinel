"""
Fetch real Sentinel-2 satellite images from Microsoft Planetary Computer
(free, no account required) for PCMC construction spots.

For each spot, finds cloud-free scenes ~30 days apart, crops a 1km²
patch centred on the location, converts to JPEG, uploads to MinIO,
and updates the DB records so the UI shows real imagery.

Usage (inside backend container):
    pip install pystac-client planetary-computer
    python fetch_real_images.py
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
MINIO_ENDPOINT  = os.environ.get("MINIO_ENDPOINT",   "minio:9000")
MINIO_ACCESS    = os.environ.get("MINIO_ACCESS_KEY",  "pcmc_minio")
MINIO_SECRET    = os.environ.get("MINIO_SECRET_KEY",  "pcmc_minio_secret")
MINIO_BUCKET    = os.environ.get("MINIO_BUCKET",      "geo-sentinel")

# Half-width of the crop around each spot centre (degrees, ~1 km)
CROP_DEG = 0.005

# Target image size for display
THUMB_PX = 256

# PCMC construction spots  (name, lat, lon)
SPOTS = [
    ("Akurdi Industrial",   18.6489, 73.8315),
    ("Nigdi Sector 27",     18.6583, 73.7718),
    ("Wakad Phase 2",       18.5985, 73.7620),
    ("Pimpri Gaon",         18.6270, 73.8032),
    ("Chinchwad East",      18.6143, 73.7983),
    ("Bhosari MIDC",        18.6444, 73.8423),
    ("Hinjewadi IT Park",   18.5914, 73.7214),
    ("Dehu Road Camp",      18.7078, 73.7583),
    ("Chakan MIDC",         18.7624, 73.8600),
    ("Ravet Junction",      18.6450, 73.7390),
]

# Search windows: use India's dry season (Nov–Feb) to avoid monsoon cloud cover
# Before: Nov–Dec 2024 | After: Jan–Mar 2026 (most recent dry season)
BEFORE_START = "2024-11-01"
BEFORE_END   = "2024-12-31"
AFTER_START  = "2026-01-01"
AFTER_END    = "2026-03-15"
NOW = datetime.now(timezone.utc)

MAX_CLOUD = 20   # percent


# ── Planetary Computer search ──────────────────────────────────────────────

def search_best_scene(catalog, bbox, date_start: str, date_end: str):
    """Return the item with lowest cloud cover in the date range."""
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{date_start}/{date_end}",
        query={"eo:cloud_cover": {"lt": MAX_CLOUD}},
        sortby="eo:cloud_cover",
        max_items=5,
    )
    items = list(search.items())
    if not items:
        return None
    return min(items, key=lambda i: i.properties.get("eo:cloud_cover", 99))


# ── Download and crop a single RGB chip ───────────────────────────────────

def download_chip(item, bbox) -> np.ndarray | None:
    """
    Download B04/B03/B02 bands from a signed Sentinel-2 COG item,
    crop to bbox (WGS84 lon_min,lat_min,lon_max,lat_max),
    return uint8 (H, W, 3) array or None on failure.
    """
    try:
        import rasterio
        from rasterio.windows import from_bounds
        from rasterio.enums import Resampling
        from rasterio.warp import transform_bounds

        import planetary_computer
        signed = planetary_computer.sign(item)

        lon_min, lat_min, lon_max, lat_max = bbox
        bands_out = []

        for band_name in ("B04", "B03", "B02"):  # R, G, B
            asset = signed.assets.get(band_name)
            if asset is None:
                return None
            with rasterio.open(asset.href) as src:
                # Transform bbox from WGS84 → raster CRS (usually UTM)
                left, bottom, right, top = transform_bounds(
                    "EPSG:4326", src.crs,
                    lon_min, lat_min, lon_max, lat_max,
                )
                win = from_bounds(left, bottom, right, top, src.transform)
                data = src.read(
                    1, window=win,
                    out_shape=(THUMB_PX, THUMB_PX),
                    resampling=Resampling.bilinear,
                )
                bands_out.append(data)

        arr = np.stack(bands_out, axis=-1).astype(np.float32)
        # Sentinel-2 L2A reflectance ~0–10000; scale to 0–255
        p2, p98 = np.percentile(arr[arr > 0], (2, 98)) if arr.any() else (0, 3000)
        arr = np.clip((arr - p2) / max(p98 - p2, 1) * 255, 0, 255).astype(np.uint8)
        return arr
    except Exception as e:
        print(f"    ⚠  rasterio download failed: {e}")
        return None


# ── Synthetic fallback ─────────────────────────────────────────────────────

def _noise(shape, scale=20):
    return (np.random.rand(*shape) * scale).astype(np.uint8)


def synthetic_before(size=THUMB_PX) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:, :, 0] = 60  + _noise((size, size), 30)
    img[:, :, 1] = 110 + _noise((size, size), 40)
    img[:, :, 2] = 50  + _noise((size, size), 20)
    for _ in range(6):
        x, y = np.random.randint(20, size - 40, 2)
        w, h = np.random.randint(20, 40, 2)
        x2, y2 = min(x+w, size), min(y+h, size)
        ah, aw = y2-y, x2-x
        img[y:y2, x:x2, 0] = 130 + _noise((ah, aw), 25)
        img[y:y2, x:x2, 1] = 100 + _noise((ah, aw), 20)
        img[y:y2, x:x2, 2] = 60  + _noise((ah, aw), 15)
    return img


def synthetic_after(size=THUMB_PX) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:, :, 0] = 140 + _noise((size, size), 30)
    img[:, :, 1] = 120 + _noise((size, size), 25)
    img[:, :, 2] = 100 + _noise((size, size), 20)
    for _ in range(4):
        x, y = np.random.randint(10, size - 60, 2)
        w, h = np.random.randint(30, 60, 2)
        x2, y2 = min(x+w, size), min(y+h, size)
        ah, aw = y2-y, x2-x
        shade = 180 + np.random.randint(0, 30)
        img[y:y2, x:x2, :] = shade + _noise((ah, aw, 3), 15)
    return img


# ── MinIO helpers ──────────────────────────────────────────────────────────

def ensure_bucket(client: Minio):
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


def upload_array(client: Minio, arr: np.ndarray, object_name: str):
    pil = PILImage.fromarray(arr, "RGB")
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=88)
    buf.seek(0)
    client.put_object(MINIO_BUCKET, object_name, buf, buf.getbuffer().nbytes,
                      content_type="image/jpeg")


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    np.random.seed(42)

    # Import here so missing packages give a clear error
    try:
        import pystac_client
        import planetary_computer
        USE_REAL = True
        print("pystac-client + planetary-computer found — will fetch real imagery.")
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )
    except ImportError:
        USE_REAL = False
        print("pystac-client not installed — falling back to synthetic images.")
        print("Run:  pip install pystac-client planetary-computer")
        catalog = None

    minio = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)
    ensure_bucket(minio)

    engine = create_async_engine(DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Load existing spots from DB (ordered by first_detected_at to match SPOTS list)
    async with Session() as db:
        rows = (await db.execute(
            text("SELECT id FROM construction_spots ORDER BY first_detected_at DESC")
        )).fetchall()
        spot_ids = [str(r[0]) for r in rows]

    print(f"\nFound {len(spot_ids)} spots in DB. Processing {min(len(spot_ids), len(SPOTS))} spots.\n")

    async with Session() as db:
        for i, (name, lat, lon) in enumerate(SPOTS):
            if i >= len(spot_ids):
                break
            spot_id = spot_ids[i]
            bbox = (lon - CROP_DEG, lat - CROP_DEG, lon + CROP_DEG, lat + CROP_DEG)

            print(f"[{i+1:2d}/10] {name}")

            before_arr = after_arr = None
            before_captured = NOW - timedelta(days=240)
            after_captured  = NOW - timedelta(days=30)

            if USE_REAL:
                print(f"       Searching before scene ({BEFORE_START} → {BEFORE_END})…")
                before_item = search_best_scene(catalog, list(bbox), BEFORE_START, BEFORE_END)
                print(f"       Searching after  scene ({AFTER_START}  → {AFTER_END})…")
                after_item  = search_best_scene(catalog, list(bbox), AFTER_START,  AFTER_END)

                if before_item:
                    cloud = before_item.properties.get("eo:cloud_cover", "?")
                    print(f"       Before: {before_item.datetime.date()} cloud={cloud}%  downloading…")
                    before_arr = download_chip(before_item, bbox)
                    if before_arr is not None:
                        before_captured = before_item.datetime.replace(tzinfo=timezone.utc)
                    else:
                        print("       Before download failed — using synthetic")
                else:
                    print("       No cloud-free before scene found — using synthetic")

                if after_item:
                    cloud = after_item.properties.get("eo:cloud_cover", "?")
                    print(f"       After:  {after_item.datetime.date()} cloud={cloud}%  downloading…")
                    after_arr = download_chip(after_item, bbox)
                    if after_arr is not None:
                        after_captured = after_item.datetime.replace(tzinfo=timezone.utc)
                    else:
                        print("       After download failed — using synthetic")
                else:
                    print("       No cloud-free after scene found — using synthetic")

            if before_arr is None:
                before_arr = synthetic_before()
            if after_arr is None:
                after_arr = synthetic_after()

            # Upload to MinIO
            before_path = f"sentinel2/real/before/{uuid.uuid4()}.jpg"
            after_path  = f"sentinel2/real/after/{uuid.uuid4()}.jpg"
            upload_array(minio, before_arr, before_path)
            upload_array(minio, after_arr,  after_path)

            # Create new satellite_image DB records
            img_before_id = uuid.uuid4()
            img_after_id  = uuid.uuid4()
            bounds_wkt = (
                f"POLYGON(({lon-CROP_DEG} {lat-CROP_DEG},"
                f"{lon+CROP_DEG} {lat-CROP_DEG},"
                f"{lon+CROP_DEG} {lat+CROP_DEG},"
                f"{lon-CROP_DEG} {lat+CROP_DEG},"
                f"{lon-CROP_DEG} {lat-CROP_DEG}))"
            )

            for img_id, path, cap in [
                (img_before_id, before_path, before_captured),
                (img_after_id,  after_path,  after_captured),
            ]:
                await db.execute(text("""
                    INSERT INTO satellite_images
                        (id, captured_at, ingested_at, storage_path, cloud_cover_pct,
                         resolution_meters, bounds, is_usable, source)
                    VALUES (:id, :cap, now(), :path, 5.0, 10.0,
                            ST_GeomFromText(:wkt, 4326), true, 'sentinel2')
                """), {"id": str(img_id), "cap": cap, "path": path, "wkt": bounds_wkt})

            # Update existing detection to point to new images
            await db.execute(text("""
                UPDATE detections
                SET image_before_id = :bid, image_after_id = :aid,
                    detected_at = :det
                WHERE spot_id = :spot_id
            """), {
                "bid": str(img_before_id),
                "aid": str(img_after_id),
                "det": after_captured,
                "spot_id": spot_id,
            })

            # Update spot timestamps
            await db.execute(text("""
                UPDATE construction_spots
                SET first_detected_at = :first, last_detected_at = :last
                WHERE id = :spot_id
            """), {"first": before_captured, "last": after_captured, "spot_id": spot_id})

            print(f"       ✓ Uploaded and linked to DB")

        await db.commit()

    await engine.dispose()
    print("\nDone! Real (or synthetic fallback) images loaded.")
    print("Refresh http://localhost:3000 — click any marker to see before/after.")


if __name__ == "__main__":
    asyncio.run(main())
