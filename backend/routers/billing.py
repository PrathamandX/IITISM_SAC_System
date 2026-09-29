from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import check_hostel_access, get_current_user, require_roles
from backend.database import get_db
from backend.models import MessCharge, MessManagerCheque, Payment, Role, Room, Student, User
from backend.schemas.common import Month
from backend.schemas.finance import (
    ChequeIssue, ChequeOut, DuesOut, MessChargeCreate, MessChargeOut, MessSheetRow, PaymentCreate, PaymentOut,
)
from backend.services import billing

router = APIRouter(prefix="/api", tags=["Mess charges, dues & payments"])


def _student_for(db: Session, roll_no: str, user: User) -> Student:
    student = billing.get_student_by_roll(db, roll_no)
    if user.role == Role.student and user.student_id != student.id:
        raise HTTPException(403, "You can only access your own dues")
    check_hostel_access(user, student.room.hostel_id)
    return student


@router.post("/mess-charges", response_model=MessChargeOut, status_code=201)
def enter_mess_charge(data: MessChargeCreate, db: Session = Depends(get_db),
                      user: User = Depends(require_roles(Role.mess_manager))):
    """Mess manager inputs the total monthly mess charge of a student."""
    student = _student_for(db, data.roll_no, user)
    if db.scalar(select(Payment).where(Payment.student_id == student.id, Payment.month == data.month)):
        raise HTTPException(409, "Dues for this month are already paid; the charge can no longer change")
    charge = db.scalar(select(MessCharge).where(MessCharge.student_id == student.id, MessCharge.month == data.month))
    if charge:
        charge.amount, charge.entered_by = data.amount, user.id
    else:
        charge = MessCharge(student_id=student.id, month=data.month, amount=data.amount, entered_by=user.id)
        db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge


@router.get("/mess-charges", response_model=list[MessChargeOut])
def list_mess_charges(month: Month, db: Session = Depends(get_db), user: User = Depends(
        require_roles(Role.mess_manager, Role.clerk, Role.warden, Role.chairman))):
    query = select(MessCharge).where(MessCharge.month == month)
    if user.role != Role.chairman:
        query = query.join(Student).join(Room).where(Room.hostel_id == user.hostel_id)
    return db.scalars(query).all()


@router.get("/dues", response_model=DuesOut)
def get_dues(roll_no: str, month: Month, db: Session = Depends(get_db), user: User = Depends(
        require_roles(Role.student, Role.clerk, Role.warden, Role.chairman))):
    """Total due = mess charge + amenity charge + room rent."""
    return billing.compute_dues(db, _student_for(db, roll_no, user), month)


@router.post("/payments", response_model=PaymentOut, status_code=201)
def pay_dues(data: PaymentCreate, db: Session = Depends(get_db),
             user: User = Depends(require_roles(Role.student, Role.clerk))):
    """Student pays dues (online, or at the counter via the clerk). The amount is always computed server-side."""
    return billing.record_payment(db, _student_for(db, data.roll_no, user), data.month, user)


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(month: Month | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(Payment).order_by(Payment.paid_at.desc())
    if month:
        query = query.where(Payment.month == month)
    if user.role == Role.student:
        query = query.where(Payment.student_id == user.student_id)
    elif user.role in (Role.clerk, Role.warden, Role.mess_manager):
        query = query.where(Payment.hostel_id == user.hostel_id)
    return db.scalars(query).all()


@router.get("/mess-sheet", response_model=list[MessSheetRow])
def mess_sheet(month: Month = Query(...), db: Session = Depends(get_db),
               _=Depends(require_roles(Role.chairman, Role.clerk))):
    """Printable sheet with the total amount due to each mess manager, with a signature column."""
    return billing.mess_manager_sheet(db, month)


@router.post("/mess-sheet/cheques", response_model=ChequeOut, status_code=201)
def issue_cheque(data: ChequeIssue, db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman))):
    return billing.issue_mess_cheque(db, data.hostel_id, data.month)


@router.post("/mess-sheet/cheques/{cheque_id}/sign", response_model=ChequeOut)
def sign_cheque(cheque_id: int, db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman))):
    """Record that the mess manager has signed the sheet on receiving the cheque."""
    cheque = db.get(MessManagerCheque, cheque_id)
    if not cheque:
        raise HTTPException(404, "Cheque not found")
    cheque.signed = True
    db.commit()
    return cheque


@router.get("/mess-sheet/cheques", response_model=list[ChequeOut])
def list_cheques(month: Month, db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman, Role.clerk))):
    return db.scalars(select(MessManagerCheque).where(MessManagerCheque.month == month)).all()
