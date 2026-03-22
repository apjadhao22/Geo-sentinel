import pytest
from datetime import datetime, timezone
from app.models import User, ConstructionSpot, AuditLog
from app.services.auth_service import hash_password


@pytest.mark.asyncio
async def test_full_review_lifecycle(db_session):
    """Test: flag → mark legal → grace period → review pending"""
    # Create officer
    officer = User(username="test_officer", password_hash=hash_password("test"), full_name="Test", role="reviewer")
    db_session.add(officer)
    await db_session.flush()

    # Create flagged spot
    spot = ConstructionSpot(
        geometry="SRID=4326;POLYGON((73.79 18.62, 73.80 18.62, 73.80 18.63, 73.79 18.63, 73.79 18.62))",
        status="flagged",
        first_detected_at=datetime.now(timezone.utc),
        last_detected_at=datetime.now(timezone.utc),
        confidence_score=0.8,
        version=1,
    )
    db_session.add(spot)
    await db_session.flush()
    assert spot.status == "flagged"

    # Mark legal
    from app.services.spot_service import review_spot
    updated = await review_spot(db_session, spot.id, "marked_legal", 1, officer, notes="Permit #123")
    assert updated.status == "legal"
    assert updated.grace_period_until is not None
    assert updated.version == 2

    # Verify audit log created
    from sqlalchemy import select
    result = await db_session.execute(select(AuditLog).where(AuditLog.spot_id == spot.id))
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "marked_legal"
    assert logs[0].notes == "Permit #123"
