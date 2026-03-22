from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class ImageryProvider(ABC):
    @abstractmethod
    async def search_images(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Search for available images in the given bounding box and date range."""
        ...

    @abstractmethod
    async def download_image(self, image_id: str, output_path: str) -> str:
        """Download an image to the given path. Returns the local file path."""
        ...
