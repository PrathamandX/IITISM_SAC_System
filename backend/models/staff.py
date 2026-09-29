import enum
from datetime import date

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class StaffRole(str, enum.Enum):
    attendant = "attendant"
    gardener = "gardener"


class TemporaryStaff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    phone: Mapped[str] = mapped_column(String(20))
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole))
    daily_pay: Mapped[float] = mapped_column(Numeric(10, 2))
    joined_on: Mapped[date] = mapped_column(default=date.today)
    # Departed staff are deactivated rather than hard-deleted so past salary records stay auditable.
    is_active: Mapped[bool] = mapped_column(default=True)

    hostel = relationship("Hostel", back_populates="staff")
    leaves = relationship("Leave", back_populates="staff")
    salaries = relationship("Salary", back_populates="staff")


class Leave(Base):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    start_date: Mapped[date]
    end_date: Mapped[date]

    staff = relationship("TemporaryStaff", back_populates="leaves")


class Salary(Base):
    __tablename__ = "salaries"
    __table_args__ = (UniqueConstraint("staff_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    days_worked: Mapped[int]
    amount_payable: Mapped[float] = mapped_column(Numeric(10, 2))
    cheque_no: Mapped[str] = mapped_column(String(30), unique=True)

    staff = relationship("TemporaryStaff", back_populates="salaries")
