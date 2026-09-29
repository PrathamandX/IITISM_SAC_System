from datetime import date

from pydantic import BaseModel, Field

from backend.schemas.common import ORM, Money, Name, Phone


class HostelCreate(BaseModel):
    name: Name
    amenity_charge: Money


class HostelOut(ORM):
    id: int
    name: str
    amenity_charge: float


class RoomCreate(BaseModel):
    room_no: str = Field(min_length=1, max_length=20)
    rent: Money


class RoomOut(ORM):
    id: int
    hostel_id: int
    room_no: str
    rent: float
    is_occupied: bool


class StudentAdmission(BaseModel):
    """Details the student presents with the admission-unit note."""

    roll_no: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9]+$")
    name: Name
    address: str = Field(min_length=3, max_length=300)
    phone: Phone
    admission_note_ref: str = Field(min_length=1, max_length=100)
    hostel_id: int
    room_id: int | None = None  # if omitted, the first free room in the hostel is allotted
    password: str = Field(min_length=8, max_length=72, description="Initial login password for the student")


class StudentOut(ORM):
    id: int
    roll_no: str
    name: str
    address: str
    phone: str
    photo_path: str | None
    admission_date: date
    room_id: int | None


class AllotmentLetter(BaseModel):
    letter_no: str
    issued_on: date
    roll_no: str
    name: str
    address: str
    hostel: str
    room_no: str
    monthly_rent: float
    monthly_amenity_charge: float


class HostelOccupancy(BaseModel):
    hostel_id: int
    hostel: str
    total_rooms: int
    occupied: int
    vacant: int


class OverallOccupancy(BaseModel):
    total_rooms: int
    occupied: int
    vacant: int
    hostels: list[HostelOccupancy]
