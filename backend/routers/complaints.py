from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import check_hostel_access, get_current_user, require_roles
from backend.database import get_db
from backend.models import Complaint, ComplaintStatus, Role, User
from backend.schemas.complaint import ATRCreate, ComplaintCreate, ComplaintOut

router = APIRouter(prefix="/api/complaints", tags=["Complaints & ATR"])


@router.post("", response_model=ComplaintOut, status_code=201)
def raise_complaint(data: ComplaintCreate, db: Session = Depends(get_db),
                    user: User = Depends(require_roles(Role.student))):
    student = user.student
    if not student or not student.room:
        raise HTTPException(400, "You must have a room allotted to raise a complaint")
    complaint = Complaint(student_id=student.id, hostel_id=student.room.hostel_id, **data.model_dump())
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("", response_model=list[ComplaintOut])
def list_complaints(status: ComplaintStatus | None = None, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    query = select(Complaint).order_by(Complaint.created_at.desc())
    if status:
        query = query.where(Complaint.status == status)
    if user.role == Role.student:
        query = query.where(Complaint.student_id == user.student_id)
    elif user.role in (Role.warden, Role.clerk):
        query = query.where(Complaint.hostel_id == user.hostel_id)
    elif user.role not in (Role.chairman, Role.controlling_warden):
        raise HTTPException(403, "You are not allowed to view complaints")
    return db.scalars(query).all()


@router.post("/{complaint_id}/atr", response_model=ComplaintOut)
def post_atr(complaint_id: int, data: ATRCreate, db: Session = Depends(get_db),
             user: User = Depends(require_roles(Role.warden))):
    """Warden posts an Action Taken Report (ATR) against a complaint."""
    complaint = db.get(Complaint, complaint_id)
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    check_hostel_access(user, complaint.hostel_id)
    complaint.atr = data.atr
    if data.resolve:
        complaint.status, complaint.resolved_at = ComplaintStatus.resolved, datetime.utcnow()
    db.commit()
    db.refresh(complaint)
    return complaint
