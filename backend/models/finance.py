from datetime import date, datetime

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class MessCharge(Base):
    __tablename__ = "mess_charges"
    __table_args__ = (UniqueConstraint("student_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    month: Mapped[str] = mapped_column(String(7))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    student = relationship("Student")


class Payment(Base):
    """A student's payment of monthly dues (mess + amenity + rent)."""

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("student_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    month: Mapped[str] = mapped_column(String(7))
    mess_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    amenity_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    rent_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    total: Mapped[float] = mapped_column(Numeric(10, 2))
    received_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    paid_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    student = relationship("Student")


class MessManagerCheque(Base):
    """Mess money collected from a hostel's students, handed to its mess manager by cheque."""

    __tablename__ = "mess_manager_cheques"
    __table_args__ = (UniqueConstraint("hostel_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    mess_manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month: Mapped[str] = mapped_column(String(7))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    cheque_no: Mapped[str] = mapped_column(String(30), unique=True)
    signed: Mapped[bool] = mapped_column(default=False)

    hostel = relationship("Hostel")
    mess_manager = relationship("User")


class AnnualGrant(Base):
    __tablename__ = "annual_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(unique=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    received_on: Mapped[date] = mapped_column(default=date.today)


class GrantAllocation(Base):
    __tablename__ = "grant_allocations"
    __table_args__ = (UniqueConstraint("year", "hostel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(ForeignKey("annual_grants.year"))
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))

    hostel = relationship("Hostel")


class Expenditure(Base):
    """Expenditure entered by a hall warden against the hall's grant allocation."""

    __tablename__ = "expenditures"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    year: Mapped[int]
    category: Mapped[str] = mapped_column(String(50))  # e.g. upkeep, garden
    description: Mapped[str] = mapped_column(String(300))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    spent_on: Mapped[date] = mapped_column(default=date.today)
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class PettyExpense(Base):
    __tablename__ = "petty_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(300))  # repairs, newspapers, magazines
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    spent_on: Mapped[date] = mapped_column(default=date.today)
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
