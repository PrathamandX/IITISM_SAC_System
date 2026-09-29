import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import check_hostel_access, get_current_user, hash_password, require_roles
from backend.database import get_db
from backend.models import Hostel, Role, Room, Student, User
from backend.schemas.hostel import AllotmentLetter, StudentAdmission, StudentOut

router = APIRouter(prefix="/api/students", tags=["Students & admission"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static" / "uploads"
ALLOWED_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
MAX_PHOTO_BYTES = 2 * 1024 * 1024


def get_student(db: Session, roll_no: str, user: User) -> Student:
    """Load a student and enforce: students see only themselves, hostel staff only their hostel."""
    student = db.scalar(select(Student).where(Student.roll_no == roll_no))
    if not student:
        raise HTTPException(404, "Student not found")
    if user.role == Role.student and user.student_id != student.id:
        raise HTTPException(403, "You can only access your own record")
    if student.room:
        check_hostel_access(user, student.room.hostel_id)
    return student


@router.post("", response_model=StudentOut, status_code=201)
def admit_student(data: StudentAdmission, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(Role.clerk, Role.chairman))):
    """Register an admitted student and allot a hostel and room (activity + sequence diagram)."""
    check_hostel_access(user, data.hostel_id)
    if not db.get(Hostel, data.hostel_id):
        raise HTTPException(404, "Hostel not found")
    if db.scalar(select(Student).where(Student.roll_no == data.roll_no)) or \
            db.scalar(select(User).where(User.username == data.roll_no)):
        raise HTTPException(409, "A student with this roll number already exists")

    if data.room_id:
        room = db.get(Room, data.room_id)
        if not room or room.hostel_id != data.hostel_id:
            raise HTTPException(400, "Room does not belong to the selected hostel")
    else:
        room = next((r for r in db.scalars(select(Room).where(Room.hostel_id == data.hostel_id).order_by(Room.id))
                     if not r.is_occupied), None)
    if not room or room.is_occupied:
        raise HTTPException(409, "No vacant room available")

    student = Student(**data.model_dump(exclude={"hostel_id", "room_id", "password"}), room_id=room.id)
    db.add(student)
    db.flush()
    db.add(User(username=data.roll_no, full_name=data.name, role=Role.student, student_id=student.id,
                hostel_id=data.hostel_id, password_hash=hash_password(data.password)))
    db.commit()
    db.refresh(student)
    return student


@router.get("", response_model=list[StudentOut])
def list_students(hostel_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(
        require_roles(Role.chairman, Role.controlling_warden, Role.warden, Role.clerk, Role.mess_manager))):
    if user.hostel_id and user.role != Role.chairman:
        hostel_id = user.hostel_id
    query = select(Student).order_by(Student.roll_no)
    if hostel_id:
        query = query.join(Room).where(Room.hostel_id == hostel_id)
    return db.scalars(query).all()


@router.get("/me", response_model=StudentOut)
def my_profile(user: User = Depends(require_roles(Role.student))):
    return user.student


@router.get("/{roll_no}/allotment-letter", response_model=AllotmentLetter)
def allotment_letter(roll_no: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    student = get_student(db, roll_no, user)
    if not student.room:
        raise HTTPException(400, "No room allotted")
    return AllotmentLetter(
        letter_no=f"SAC/ALLOT/{student.admission_date.year}/{student.id:05d}", issued_on=date.today(),
        roll_no=student.roll_no, name=student.name, address=student.address,
        hostel=student.room.hostel.name, room_no=student.room.room_no,
        monthly_rent=float(student.room.rent), monthly_amenity_charge=float(student.room.hostel.amenity_charge),
    )


@router.post("/{roll_no}/photo", response_model=StudentOut)
async def upload_photo(roll_no: str, photo: UploadFile = File(...), db: Session = Depends(get_db),
                       user: User = Depends(require_roles(Role.clerk, Role.chairman, Role.student))):
    student = get_student(db, roll_no, user)
    if photo.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(400, "Photo must be a JPEG or PNG image")
    content = await photo.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "Photo must be smaller than 2 MB")
    name = f"{uuid.uuid4().hex}{ALLOWED_PHOTO_TYPES[photo.content_type]}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / name).write_bytes(content)
    student.photo_path = f"/static/uploads/{name}"
    db.commit()
    return student
