import httpx
from datetime import datetime
from typing import Any
from ingestion.provider_base import ImageryProvider


class Sentinel2Provider(ImageryProvider):
    TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    async def _get_token(self) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            response.raise_for_status()
            self._token = response.json()["access_token"]
            return self._token

    async def search_images(
        self,
        bbox: tuple[float, float, float, float],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
    ) -> list[dict[str, Any]]:
        token = await self._get_token()
        west, south, east, north = bbox
        filter_str = (
            f"Collection/Name eq 'SENTINEL-2' "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
            f"{west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))') "
            f"and ContentDate/Start gt {start_date.isoformat()}Z "
            f"and ContentDate/Start lt {end_date.isoformat()}Z "
            f"and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"and att/Value lt {max_cloud_cover})"
        )
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.CATALOG_URL,
                params={"$filter": filter_str, "$top": 5, "$orderby": "ContentDate/Start desc"},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json().get("value", [])

    async def download_image(self, image_id: str, output_path: str) -> str:
        token = await self._get_token()
        download_url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({image_id})/$value"
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "GET",
                download_url,
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
            ) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
        return output_path
