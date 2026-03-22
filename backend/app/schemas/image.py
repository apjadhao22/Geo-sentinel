from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ImageOut(BaseModel):
    id: UUID
    captured_at: datetime
    cloud_cover_pct: float
    resolution_meters: float
    is_usable: bool
    source: str

    class Config:
        from_attributes = True


class ImageCompare(BaseModel):
    before_url: str
    after_url: str
    before_captured_at: datetime
    after_captured_at: datetime


class ImageTileResponse(BaseModel):
    url: str
