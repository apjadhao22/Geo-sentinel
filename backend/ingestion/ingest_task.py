import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.storage import upload_image
from ingestion.sentinel2_provider import Sentinel2Provider
from ingestion.planet_provider import PlanetProvider

# PCMC bounding box (approximate)
PCMC_BBOX = (73.7100, 18.5700, 73.8900, 18.6900)


def get_provider():
    if settings.imagery_provider == "sentinel2":
        return Sentinel2Provider(settings.sentinel2_client_id, settings.sentinel2_client_secret)
    elif settings.imagery_provider == "planet":
        return PlanetProvider(api_key=os.getenv("PLANET_API_KEY", ""))
    raise ValueError(f"Unknown provider: {settings.imagery_provider}")


async def run_ingestion(max_retries: int = 3):
    provider = get_provider()
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=2)

    images = None
    last_error = None
    for attempt in range(max_retries):
        try:
            images = await provider.search_images(
                bbox=PCMC_BBOX,
                start_date=start_date,
                end_date=end_date,
                max_cloud_cover=30.0,
            )
            break
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt * 5)  # Exponential backoff: 5s, 10s

    if images is None:
        return {"status": "error", "message": f"Ingestion failed after {max_retries} retries: {last_error}"}

    if not images:
        return {"status": "no_images", "message": "No usable images found"}

    results = []
    # Process only the latest image (images[:1] — expand slice to process multiple in future)
    img_meta = images[0]
    image_id = img_meta.get("Id") or img_meta.get("id")
    if not image_id:
        return {"status": "error", "message": "Image metadata missing ID field"}

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await provider.download_image(image_id, tmp_path)
        object_name = f"raw/{end_date.strftime('%Y/%m/%d')}/{uuid4()}.tif"
        upload_image(object_name, tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    results.append({
        "image_id": image_id,
        "storage_path": object_name,
        "captured_at": img_meta.get("ContentDate", {}).get("Start"),
    })

    return {"status": "success", "images": results}
