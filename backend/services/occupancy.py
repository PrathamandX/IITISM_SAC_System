from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Hostel


def hostel_occupancy(hostel: Hostel) -> dict:
    total = len(hostel.rooms)
    occupied = sum(1 for r in hostel.rooms if r.is_occupied)
    return {"hostel_id": hostel.id, "hostel": hostel.name, "total_rooms": total,
            "occupied": occupied, "vacant": total - occupied}


def overall_occupancy(db: Session) -> dict:
    hostels = [hostel_occupancy(h) for h in db.scalars(select(Hostel).order_by(Hostel.name))]
    total = sum(h["total_rooms"] for h in hostels)
    occupied = sum(h["occupied"] for h in hostels)
    return {"total_rooms": total, "occupied": occupied, "vacant": total - occupied, "hostels": hostels}
