from datetime import datetime
from typing import Any
from ingestion.provider_base import ImageryProvider


class PlanetProvider(ImageryProvider):
    """Phase 2 stub — to be implemented when Planet Labs subscription is active."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search_images(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Planet Labs provider not yet implemented. Activate Phase 2.")

    async def download_image(self, image_id: str, output_path: str) -> str:
        raise NotImplementedError("Planet Labs provider not yet implemented. Activate Phase 2.")
