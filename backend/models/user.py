import enum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Role(str, enum.Enum):
    chairman = "chairman"                      # SAC chairman: admin, grants, petty expenses
    controlling_warden = "controlling_warden"  # hostel dean: overall occupancy
    warden = "warden"                          # hall warden: occupancy, ATR, expenditure, statement
    clerk = "clerk"                            # hostel manager / caretaker: admission, staff, leave, payments
    mess_manager = "mess_manager"              # enters monthly mess charges
    student = "student"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(Enum(Role))
    hostel_id: Mapped[int | None] = mapped_column(ForeignKey("hostels.id"))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"))
    is_active: Mapped[bool] = mapped_column(default=True)

    hostel = relationship("Hostel")
    student = relationship("Student")
