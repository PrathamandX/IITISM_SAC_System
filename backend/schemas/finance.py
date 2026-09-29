from datetime import date, datetime

from pydantic import BaseModel, Field

from backend.schemas.common import ORM, Money, Month

Year = Field(ge=2000, le=2100)


class MessChargeCreate(BaseModel):
    roll_no: str
    month: Month
    amount: Money


class MessChargeOut(ORM):
    id: int
    student_id: int
    month: str
    amount: float


class DuesOut(BaseModel):
    roll_no: str
    month: str
    mess_charge: float
    amenity_charge: float
    room_rent: float
    total_due: float
    paid: bool


class PaymentCreate(BaseModel):
    roll_no: str
    month: Month


class PaymentOut(ORM):
    id: int
    student_id: int
    month: str
    total: float
    paid_at: datetime


class MessSheetRow(BaseModel):
    hostel_id: int
    hostel: str
    mess_manager: str | None
    amount_due: float
    cheque_no: str | None
    signed: bool


class ChequeIssue(BaseModel):
    hostel_id: int
    month: Month


class ChequeOut(ORM):
    id: int
    hostel_id: int
    month: str
    amount: float
    cheque_no: str
    signed: bool


class GrantCreate(BaseModel):
    year: int = Year
    amount: Money


class GrantOut(ORM):
    id: int
    year: int
    amount: float
    received_on: date


class AllocationCreate(BaseModel):
    year: int = Year
    hostel_id: int
    amount: Money


class AllocationOut(ORM):
    id: int
    year: int
    hostel_id: int
    amount: float


class ExpenditureCreate(BaseModel):
    hostel_id: int
    year: int = Year
    category: str = Field(min_length=2, max_length=50, examples=["upkeep"])
    description: str = Field(min_length=2, max_length=300)
    amount: Money
    spent_on: date | None = None


class ExpenditureOut(ORM):
    id: int
    hostel_id: int
    year: int
    category: str
    description: str
    amount: float
    spent_on: date


class PettyExpenseCreate(BaseModel):
    description: str = Field(min_length=2, max_length=300)
    amount: Money
    spent_on: date | None = None


class PettyExpenseOut(ORM):
    id: int
    description: str
    amount: float
    spent_on: date


class StatementLine(BaseModel):
    head: str
    amount: float


class Statement(BaseModel):
    year: int
    scope: str
    income: list[StatementLine]
    expenditure: list[StatementLine]
    total_income: float
    total_expenditure: float
    balance: float
    generated_at: datetime
