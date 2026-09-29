import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ComplaintType(str, enum.Enum):
    repair = "repair"      # RepairComplaint: fused light, water tap, filter, room repair
    behavior = "behavior"  # BehaviorComplaint: attendants, mess staff


class ComplaintStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    type: Mapped[ComplaintType] = mapped_column(Enum(ComplaintType))
    repair_type: Mapped[str | None] = mapped_column(String(100))
    against: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ComplaintStatus] = mapped_column(Enum(ComplaintStatus), default=ComplaintStatus.open)
    atr: Mapped[str | None] = mapped_column(Text)  # Action Taken Report posted by the warden
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    resolved_at: Mapped[datetime | None]

    student = relationship("Student", back_populates="complaints")
