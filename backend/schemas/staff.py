from datetime import date

from pydantic import BaseModel, Field, model_validator

from backend.models import StaffRole
from backend.schemas.common import ORM, Money, Month, Name, Phone


class StaffCreate(BaseModel):
    hostel_id: int
    name: Name
    address: str = Field(min_length=3, max_length=300)
    phone: Phone
    role: StaffRole
    daily_pay: Money
    joined_on: date | None = None  # defaults to today


class StaffOut(ORM):
    id: int
    hostel_id: int
    name: str
    role: StaffRole
    phone: str
    daily_pay: float
    joined_on: date
    is_active: bool


class LeaveCreate(BaseModel):
    staff_id: int
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveOut(ORM):
    id: int
    staff_id: int
    start_date: date
    end_date: date


class SalaryGenerate(BaseModel):
    hostel_id: int
    month: Month


class SalaryOut(BaseModel):
    staff_id: int
    name: str
    role: StaffRole
    month: str
    days_worked: int
    daily_pay: float
    amount_payable: float
    cheque_no: str
