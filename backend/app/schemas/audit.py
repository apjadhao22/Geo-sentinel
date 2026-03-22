from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class AuditLogOut(BaseModel):
    id: UUID
    officer_id: UUID
    spot_id: UUID
    action: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OfficerSummaryOut(BaseModel):
    officer_id: UUID
    action: str
    count: int
