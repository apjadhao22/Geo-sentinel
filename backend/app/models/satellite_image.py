import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from sqlalchemy.sql import func

from app.database import Base


class SatelliteImage(Base):
    __tablename__ = "satellite_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    captured_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    storage_path = Column(String(500), nullable=False)
    cloud_cover_pct = Column(Float, nullable=False)
    resolution_meters = Column(Float, nullable=False)
    bounds = Column(Geometry("POLYGON", srid=4326), nullable=False)
    is_usable = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=False, default="sentinel2")
