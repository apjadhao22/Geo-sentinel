from pydantic import BaseModel, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional


class SpotOut(BaseModel):
    id: UUID
    status: str
    first_detected_at: datetime
    last_detected_at: datetime
    confidence_score: float
    change_type: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    version: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class SpotDetail(SpotOut):
    notes: Optional[str] = None
    grace_period_until: Optional[datetime] = None
    review_prompted_at: Optional[datetime] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    previous_spot_id: Optional[UUID] = None


class SpotReviewRequest(BaseModel):
    action: str  # marked_legal, marked_illegal, marked_resolved, re_approved, re_flagged
    notes: Optional[str] = None
    version: int

    @model_validator(mode="after")
    def validate_notes_required(self):
        if self.action in ("marked_legal", "re_approved") and not self.notes:
            raise ValueError("Notes are required when marking as legal or re-approving")
        return self


class SpotAssignRequest(BaseModel):
    assigned_to_id: UUID


class SpotStats(BaseModel):
    flagged: int = 0
    legal: int = 0
    illegal: int = 0
    resolved: int = 0
    review_pending: int = 0


class DetectionOut(BaseModel):
    id: UUID
    spot_id: UUID
    detected_at: datetime
    comparison_interval: str
    confidence: float
    image_before_id: UUID
    image_after_id: UUID
    area_sq_meters: float

    class Config:
        from_attributes = True
