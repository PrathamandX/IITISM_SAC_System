from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import check_hostel_access, require_roles
from backend.database import get_db
from backend.models import Hostel, Leave, Role, TemporaryStaff, User
from backend.schemas.common import Month
from backend.schemas.staff import LeaveCreate, LeaveOut, SalaryGenerate, SalaryOut, StaffCreate, StaffOut
from backend.services.salary import generate_salaries, list_salaries

router = APIRouter(prefix="/api", tags=["Hostel staff, leave & salary"])

STAFF_ADMINS = (Role.clerk, Role.warden, Role.chairman)


def _get_staff(db: Session, staff_id: int, user: User) -> TemporaryStaff:
    staff = db.get(TemporaryStaff, staff_id)
    if not staff:
        raise HTTPException(404, "Staff member not found")
    check_hostel_access(user, staff.hostel_id)
    return staff


def _hostel_for(user: User, hostel_id: int | None) -> int:
    hostel_id = hostel_id or user.hostel_id
    if not hostel_id:
        raise HTTPException(400, "hostel_id is required")
    check_hostel_access(user, hostel_id)
    return hostel_id


@router.post("/staff", response_model=StaffOut, status_code=201)
def recruit_staff(data: StaffCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF_ADMINS))):
    check_hostel_access(user, data.hostel_id)
    if not db.get(Hostel, data.hostel_id):
        raise HTTPException(404, "Hostel not found")
    staff = TemporaryStaff(**data.model_dump(exclude_none=True))
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.get("/staff", response_model=list[StaffOut])
def list_staff(hostel_id: int | None = None, include_inactive: bool = False, db: Session = Depends(get_db),
               user: User = Depends(require_roles(*STAFF_ADMINS))):
    query = select(TemporaryStaff).where(TemporaryStaff.hostel_id == _hostel_for(user, hostel_id))
    if not include_inactive:
        query = query.where(TemporaryStaff.is_active)
    return db.scalars(query.order_by(TemporaryStaff.name)).all()


@router.delete("/staff/{staff_id}", status_code=204)
def remove_staff(staff_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF_ADMINS))):
    """Staff leaves: the record is removed from active use (kept for salary audit)."""
    _get_staff(db, staff_id, user).is_active = False
    db.commit()


@router.post("/leaves", response_model=LeaveOut, status_code=201)
def enter_leave(data: LeaveCreate, db: Session = Depends(get_db),
                user: User = Depends(require_roles(Role.clerk, Role.chairman))):
    """Caretaker/clerk enters leave taken by an attendant or gardener."""
    staff = _get_staff(db, data.staff_id, user)
    if not staff.is_active:
        raise HTTPException(400, "Staff member is no longer employed")
    overlap = db.scalar(select(Leave).where(Leave.staff_id == staff.id, Leave.start_date <= data.end_date,
                                            Leave.end_date >= data.start_date))
    if overlap:
        raise HTTPException(409, "Leave overlaps an existing leave entry")
    leave = Leave(**data.model_dump())
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.get("/leaves", response_model=list[LeaveOut])
def list_leaves(staff_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF_ADMINS))):
    return _get_staff(db, staff_id, user).leaves


@router.post("/salaries/generate", response_model=list[SalaryOut])
def generate_salary_list(data: SalaryGenerate, db: Session = Depends(get_db),
                         user: User = Depends(require_roles(Role.clerk, Role.chairman))):
    """End of month: consolidated salary list and a cheque per employee."""
    check_hostel_access(user, data.hostel_id)
    return generate_salaries(db, data.hostel_id, data.month)


@router.get("/salaries", response_model=list[SalaryOut])
def salary_list(month: Month, hostel_id: int | None = None, db: Session = Depends(get_db),
                user: User = Depends(require_roles(*STAFF_ADMINS))):
    return list_salaries(db, _hostel_for(user, hostel_id), month)
