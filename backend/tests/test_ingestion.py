import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from ingestion.provider_base import ImageryProvider
from ingestion.sentinel2_provider import Sentinel2Provider
from ingestion.planet_provider import PlanetProvider


def test_sentinel2_implements_provider():
    provider = Sentinel2Provider(client_id="test", client_secret="test")
    assert isinstance(provider, ImageryProvider)


def test_planet_implements_provider():
    provider = PlanetProvider(api_key="test")
    assert isinstance(provider, ImageryProvider)


def test_provider_has_required_methods():
    provider = Sentinel2Provider(client_id="test", client_secret="test")
    assert hasattr(provider, "search_images")
    assert hasattr(provider, "download_image")


@pytest.mark.asyncio
async def test_planet_provider_raises_not_implemented():
    provider = PlanetProvider(api_key="test")
    with pytest.raises(NotImplementedError):
        await provider.search_images(
            bbox=(73.71, 18.57, 73.89, 18.69),
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_planet_provider_download_raises_not_implemented():
    provider = PlanetProvider(api_key="test")
    with pytest.raises(NotImplementedError):
        await provider.download_image("some-id", "/tmp/out.tif")


@pytest.mark.asyncio
async def test_run_ingestion_success():
    from ingestion.ingest_task import run_ingestion
    mock_images = [{"Id": "img-001", "ContentDate": {"Start": "2026-03-22T06:00:00Z"}}]
    with (
        patch("ingestion.ingest_task.get_provider") as mock_get_provider,
        patch("ingestion.ingest_task.upload_image"),
        patch("ingestion.ingest_task.tempfile.NamedTemporaryFile"),
        patch("ingestion.ingest_task.os.path.exists", return_value=True),
        patch("ingestion.ingest_task.os.unlink"),
    ):
        provider = AsyncMock()
        provider.search_images.return_value = mock_images
        provider.download_image.return_value = "/tmp/fake.tif"
        mock_get_provider.return_value = provider

        result = await run_ingestion()

    assert result["status"] == "success"
    assert len(result["images"]) == 1
    assert result["images"][0]["image_id"] == "img-001"


@pytest.mark.asyncio
async def test_run_ingestion_all_retries_fail():
    from ingestion.ingest_task import run_ingestion
    with patch("ingestion.ingest_task.get_provider") as mock_get_provider, \
         patch("ingestion.ingest_task.asyncio.sleep"):
        provider = AsyncMock()
        provider.search_images.side_effect = Exception("API down")
        mock_get_provider.return_value = provider

        result = await run_ingestion(max_retries=2)

    assert result["status"] == "error"
    assert "retries" in result["message"]


@pytest.mark.asyncio
async def test_run_ingestion_no_images():
    from ingestion.ingest_task import run_ingestion
    with patch("ingestion.ingest_task.get_provider") as mock_get_provider:
        provider = AsyncMock()
        provider.search_images.return_value = []
        mock_get_provider.return_value = provider

        result = await run_ingestion()

    assert result["status"] == "no_images"
