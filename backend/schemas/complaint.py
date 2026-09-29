from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from backend.models import ComplaintStatus, ComplaintType
from backend.schemas.common import ORM


class ComplaintCreate(BaseModel):
    type: ComplaintType
    repair_type: str | None = Field(None, max_length=100, examples=["fused light"])
    against: str | None = Field(None, max_length=100, examples=["mess staff"])
    description: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def check_subtype(self):
        if self.type == ComplaintType.repair and not self.repair_type:
            raise ValueError("repair_type is required for a repair complaint")
        if self.type == ComplaintType.behavior and not self.against:
            raise ValueError("against is required for a behavior complaint")
        return self


class ATRCreate(BaseModel):
    atr: str = Field(min_length=5, max_length=2000)
    resolve: bool = True


class ComplaintOut(ORM):
    id: int
    student_id: int
    hostel_id: int
    type: ComplaintType
    repair_type: str | None
    against: str | None
    description: str
    status: ComplaintStatus
    atr: str | None
    created_at: datetime
    resolved_at: datetime | None
