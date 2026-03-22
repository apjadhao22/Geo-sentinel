import pytest
from datetime import datetime, timezone
from geoalchemy2.shape import from_shape
from shapely.geometry import box
from app.models.construction_spot import ConstructionSpot


@pytest.fixture
async def sample_spot(db_session):
    spot = ConstructionSpot(
        geometry=from_shape(box(73.795, 18.625, 73.798, 18.628), srid=4326),
        status="flagged",
        first_detected_at=datetime.now(timezone.utc),
        last_detected_at=datetime.now(timezone.utc),
        confidence_score=0.75,
        version=1,
    )
    db_session.add(spot)
    await db_session.flush()
    return spot


@pytest.fixture
async def auth_token(db_session, seed_users, client):
    response = await client.post("/auth/login", json={"username": "officer1", "password": "test123"})
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_review_spot_mark_legal_requires_notes(client, auth_token, sample_spot):
    response = await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_legal", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422  # notes required


@pytest.mark.asyncio
async def test_review_spot_mark_legal_with_notes(client, auth_token, sample_spot):
    response = await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_legal", "notes": "Permit #PCM-2026-001", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "legal"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_review_spot_optimistic_lock_conflict(client, auth_token, sample_spot):
    # First review succeeds
    await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_illegal", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    # Second review with stale version fails
    response = await client.patch(
        f"/spots/{sample_spot.id}/review",
        json={"action": "marked_legal", "notes": "Permit exists", "version": 1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 409
