from datetime import date

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Hostel(Base):
    __tablename__ = "hostels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    amenity_charge: Mapped[float] = mapped_column(Numeric(10, 2))  # fixed monthly amenity levy

    rooms = relationship("Room", back_populates="hostel", cascade="all, delete-orphan")
    staff = relationship("TemporaryStaff", back_populates="hostel")


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("hostel_id", "room_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    room_no: Mapped[str] = mapped_column(String(20))
    rent: Mapped[float] = mapped_column(Numeric(10, 2))  # monthly rent, higher in newer hostels

    hostel = relationship("Hostel", back_populates="rooms")
    student = relationship("Student", back_populates="room", uselist=False)

    @property
    def is_occupied(self) -> bool:
        return self.student is not None


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    roll_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    phone: Mapped[str] = mapped_column(String(20))
    photo_path: Mapped[str | None] = mapped_column(String(200))
    admission_note_ref: Mapped[str] = mapped_column(String(100))
    admission_date: Mapped[date] = mapped_column(default=date.today)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), unique=True)

    room = relationship("Room", back_populates="student")
    complaints = relationship("Complaint", back_populates="student")
