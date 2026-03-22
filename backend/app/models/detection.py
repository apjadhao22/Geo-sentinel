import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

COMPARISON_INTERVAL = SAEnum("1d", "7d", "15d", "30d", name="comparison_interval")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("construction_spots.id"), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    comparison_interval = Column(COMPARISON_INTERVAL, nullable=False)
    confidence = Column(Float, nullable=False)
    image_before_id = Column(UUID(as_uuid=True), ForeignKey("satellite_images.id"), nullable=False)
    image_after_id = Column(UUID(as_uuid=True), ForeignKey("satellite_images.id"), nullable=False)
    change_mask_path = Column(String(500), nullable=False)
    area_sq_meters = Column(Float, nullable=False)

    spot = relationship("ConstructionSpot", back_populates="detections")
    image_before = relationship("SatelliteImage", foreign_keys=[image_before_id])
    image_after = relationship("SatelliteImage", foreign_keys=[image_after_id])
