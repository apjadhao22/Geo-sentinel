import pytest
from datetime import datetime, timezone
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
