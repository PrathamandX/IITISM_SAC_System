from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Hostel, MessCharge, MessManagerCheque, Payment, Role, Student, User


def get_student_by_roll(db: Session, roll_no: str) -> Student:
    student = db.scalar(select(Student).where(Student.roll_no == roll_no))
    if not student:
        raise HTTPException(404, f"Student {roll_no} not found")
    if not student.room:
        raise HTTPException(400, f"Student {roll_no} has no room allotted")
    return student


def compute_dues(db: Session, student: Student, month: str) -> dict:
    """Total due = mess charge + amenity charge + room rent (problem statement)."""
    mess = db.scalar(select(MessCharge.amount).where(MessCharge.student_id == student.id, MessCharge.month == month))
    paid = db.scalar(select(Payment.id).where(Payment.student_id == student.id, Payment.month == month))
    mess = float(mess or 0)
    amenity = float(student.room.hostel.amenity_charge)
    rent = float(student.room.rent)
    return {
        "roll_no": student.roll_no,
        "month": month,
        "mess_charge": mess,
        "amenity_charge": amenity,
        "room_rent": rent,
        "total_due": round(mess + amenity + rent, 2),
        "paid": paid is not None,
    }


def record_payment(db: Session, student: Student, month: str, received_by: User) -> Payment:
    dues = compute_dues(db, student, month)
    if dues["paid"]:
        raise HTTPException(409, f"Dues for {month} are already paid")
    if dues["mess_charge"] == 0:
        raise HTTPException(400, f"Mess charges for {month} have not been entered yet")
    payment = Payment(
        student_id=student.id,
        hostel_id=student.room.hostel_id,
        month=month,
        mess_amount=dues["mess_charge"],
        amenity_amount=dues["amenity_charge"],
        rent_amount=dues["room_rent"],
        total=dues["total_due"],
        received_by=received_by.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def mess_collected(db: Session, hostel_id: int, month: str) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(Payment.mess_amount), 0)).where(
            Payment.hostel_id == hostel_id, Payment.month == month
        )
    )
    return float(total)


def mess_manager_sheet(db: Session, month: str) -> list[dict]:
    """Sheet of the mess money due to each hostel's mess manager, with cheque/signature status."""
    rows = []
    for hostel in db.scalars(select(Hostel).order_by(Hostel.name)):
        manager = db.scalar(select(User).where(User.hostel_id == hostel.id, User.role == Role.mess_manager))
        cheque = db.scalar(
            select(MessManagerCheque).where(MessManagerCheque.hostel_id == hostel.id, MessManagerCheque.month == month)
        )
        rows.append({
            "hostel_id": hostel.id,
            "hostel": hostel.name,
            "mess_manager": manager.full_name if manager else None,
            "amount_due": mess_collected(db, hostel.id, month),
            "cheque_no": cheque.cheque_no if cheque else None,
            "signed": cheque.signed if cheque else False,
        })
    return rows


def issue_mess_cheque(db: Session, hostel_id: int, month: str) -> MessManagerCheque:
    manager = db.scalar(select(User).where(User.hostel_id == hostel_id, User.role == Role.mess_manager))
    if not manager:
        raise HTTPException(400, "This hostel has no mess manager account")
    exists = db.scalar(
        select(MessManagerCheque).where(MessManagerCheque.hostel_id == hostel_id, MessManagerCheque.month == month)
    )
    if exists:
        raise HTTPException(409, "Cheque already issued for this hostel and month")
    amount = mess_collected(db, hostel_id, month)
    if amount <= 0:
        raise HTTPException(400, "No mess charges collected for this month")
    cheque = MessManagerCheque(
        hostel_id=hostel_id, mess_manager_id=manager.id, month=month, amount=amount,
        cheque_no=f"MESS-{month}-{hostel_id}",
    )
    db.add(cheque)
    db.commit()
    db.refresh(cheque)
    return cheque
