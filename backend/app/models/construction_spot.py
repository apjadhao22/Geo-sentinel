import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship

from app.database import Base

SPOT_STATUS = SAEnum(
    "flagged", "legal", "illegal", "resolved", "review_pending",
    name="spot_status"
)
CHANGE_TYPE = SAEnum(
    "excavation", "foundation", "new_structure", "extension", "land_clearing",
    name="change_type"
)


class ConstructionSpot(Base):
    __tablename__ = "construction_spots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    geometry = Column(Geometry("POLYGON", srid=4326), nullable=False)
    status = Column(SPOT_STATUS, nullable=False, default="flagged")
    first_detected_at = Column(DateTime(timezone=True), nullable=False)
    last_detected_at = Column(DateTime(timezone=True), nullable=False)
    grace_period_until = Column(DateTime(timezone=True), nullable=True)
    review_prompted_at = Column(DateTime(timezone=True), nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    change_type = Column(CHANGE_TYPE, nullable=True)
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    previous_spot_id = Column(UUID(as_uuid=True), ForeignKey("construction_spots.id"), nullable=True)
    version = Column(Integer, nullable=False, default=1)

    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    previous_spot = relationship("ConstructionSpot", remote_side=[id])
    detections = relationship("Detection", back_populates="spot", cascade="all, delete-orphan")
