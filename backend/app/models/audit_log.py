import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base

AUDIT_ACTION = SAEnum(
    "marked_legal", "marked_illegal", "marked_resolved", "re_approved", "re_flagged",
    name="audit_action"
)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("construction_spots.id"), nullable=False)
    action = Column(AUDIT_ACTION, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    officer = relationship("User")
    spot = relationship("ConstructionSpot")
