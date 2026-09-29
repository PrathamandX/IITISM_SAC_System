from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import check_hostel_access, get_current_user, require_roles
from backend.database import get_db
from backend.models import Hostel, Role, Room, User
from backend.schemas.hostel import HostelCreate, HostelOccupancy, HostelOut, OverallOccupancy, RoomCreate, RoomOut
from backend.services.occupancy import hostel_occupancy, overall_occupancy

router = APIRouter(prefix="/api", tags=["Hostels, rooms & occupancy"])


def get_hostel(db: Session, hostel_id: int) -> Hostel:
    hostel = db.get(Hostel, hostel_id)
    if not hostel:
        raise HTTPException(404, "Hostel not found")
    return hostel


@router.post("/hostels", response_model=HostelOut, status_code=201)
def create_hostel(data: HostelCreate, db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman))):
    if db.scalar(select(Hostel).where(Hostel.name == data.name)):
        raise HTTPException(409, "Hostel already exists")
    hostel = Hostel(**data.model_dump())
    db.add(hostel)
    db.commit()
    db.refresh(hostel)
    return hostel


@router.get("/hostels", response_model=list[HostelOut])
def list_hostels(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Hostel).order_by(Hostel.name)).all()


@router.put("/hostels/{hostel_id}", response_model=HostelOut)
def update_hostel(hostel_id: int, data: HostelCreate, db: Session = Depends(get_db),
                  _=Depends(require_roles(Role.chairman))):
    hostel = get_hostel(db, hostel_id)
    hostel.name, hostel.amenity_charge = data.name, data.amenity_charge
    db.commit()
    return hostel


@router.post("/hostels/{hostel_id}/rooms", response_model=RoomOut, status_code=201)
def add_room(hostel_id: int, data: RoomCreate, db: Session = Depends(get_db),
             _=Depends(require_roles(Role.chairman))):
    get_hostel(db, hostel_id)
    if db.scalar(select(Room).where(Room.hostel_id == hostel_id, Room.room_no == data.room_no)):
        raise HTTPException(409, "Room already exists in this hostel")
    room = Room(hostel_id=hostel_id, **data.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/hostels/{hostel_id}/rooms", response_model=list[RoomOut])
def list_rooms(hostel_id: int, vacant_only: bool = False, db: Session = Depends(get_db),
               user: User = Depends(require_roles(Role.chairman, Role.controlling_warden, Role.warden, Role.clerk))):
    check_hostel_access(user, hostel_id)
    rooms = get_hostel(db, hostel_id).rooms
    return [r for r in rooms if not (vacant_only and r.is_occupied)]


@router.get("/hostels/{hostel_id}/occupancy", response_model=HostelOccupancy)
def hostel_occupancy_view(hostel_id: int, db: Session = Depends(get_db), user: User = Depends(
        require_roles(Role.chairman, Role.controlling_warden, Role.warden, Role.clerk))):
    """Warden of each hostel finds out the occupancy of their hostel."""
    check_hostel_access(user, hostel_id)
    return hostel_occupancy(get_hostel(db, hostel_id))


@router.get("/occupancy", response_model=OverallOccupancy)
def overall_occupancy_view(db: Session = Depends(get_db),
                           _=Depends(require_roles(Role.controlling_warden, Role.chairman))):
    """Controlling warden views the overall room occupancy."""
    return overall_occupancy(db)
