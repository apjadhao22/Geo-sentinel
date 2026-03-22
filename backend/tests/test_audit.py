import pytest
from datetime import datetime, timezone
from geoalchemy2.shape import from_shape
from shapely.geometry import box
from sqlalchemy import select
from app.models import ConstructionSpot, AuditLog
from app.services.audit_service import create_audit_log, get_audit_logs


@pytest.fixture
async def officer_and_spot(db_session, seed_users):
    officer = seed_users[0]  # officer1
    spot = ConstructionSpot(
        geometry=from_shape(box(73.795, 18.625, 73.798, 18.628), srid=4326),
        status="illegal",
        first_detected_at=datetime.now(timezone.utc),
        last_detected_at=datetime.now(timezone.utc),
        confidence_score=0.8,
        version=2,
    )
    db_session.add(spot)
    await db_session.flush()
    return officer, spot


@pytest.mark.asyncio
async def test_create_audit_log(db_session, officer_and_spot):
    officer, spot = officer_and_spot
    await create_audit_log(db_session, officer_id=officer.id, spot_id=spot.id, action="marked_illegal")
    await db_session.flush()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.spot_id == spot.id)
    )
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "marked_illegal"
    assert logs[0].notes is None


@pytest.mark.asyncio
async def test_get_audit_logs_filtered_by_action(db_session, officer_and_spot):
    officer, spot = officer_and_spot
    await create_audit_log(db_session, officer_id=officer.id, spot_id=spot.id, action="marked_illegal")
    await create_audit_log(db_session, officer_id=officer.id, spot_id=spot.id, action="marked_resolved")
    await db_session.flush()

    logs = await get_audit_logs(db_session, action="marked_illegal")
    assert all(log.action == "marked_illegal" for log in logs)
