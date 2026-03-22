import uuid
from sqlalchemy import Column, String, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(SAEnum("reviewer", "admin", "super_admin", name="user_role"), nullable=False, default="reviewer")
    is_active = Column(Boolean, nullable=False, default=True)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id"), nullable=True)

    zone = relationship("Zone", back_populates="assigned_reviewer")
