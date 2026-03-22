import pytest
from datetime import datetime, timezone
from app.models import User, Zone, ConstructionSpot, SatelliteImage, Detection, AuditLog


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(username="officer1", password_hash="hashed", full_name="Test Officer", role="reviewer")
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None
    assert user.role == "reviewer"


@pytest.mark.asyncio
async def test_create_construction_spot(db_session):
    spot = ConstructionSpot(
        geometry="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        status="flagged",
        first_detected_at=datetime.now(timezone.utc),
        last_detected_at=datetime.now(timezone.utc),
        confidence_score=0.75,
        version=1,
    )
    db_session.add(spot)
    await db_session.flush()
    assert spot.id is not None
    assert spot.status == "flagged"
    assert spot.version == 1
