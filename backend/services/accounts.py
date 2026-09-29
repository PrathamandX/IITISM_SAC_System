from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import (
    AnnualGrant, Expenditure, GrantAllocation, Hostel, MessManagerCheque, Payment, PettyExpense, Salary,
    TemporaryStaff,
)


def _sum(db: Session, column, *where) -> float:
    return float(db.scalar(select(func.coalesce(func.sum(column), 0)).where(*where)))


def statement_of_accounts(db: Session, year: int, hostel_id: int | None = None) -> dict:
    """Annual consolidated statement for one hall (warden) or the whole SAC (chairman)."""
    prefix = f"{year}-%"
    hall = [Payment.hostel_id == hostel_id] if hostel_id else []

    if hostel_id:
        grant = _sum(db, GrantAllocation.amount, GrantAllocation.year == year, GrantAllocation.hostel_id == hostel_id)
        scope = db.get(Hostel, hostel_id).name
    else:
        grant = _sum(db, AnnualGrant.amount, AnnualGrant.year == year)
        scope = "SAC (all hostels)"

    income = [
        {"head": "Institute grant", "amount": grant},
        {"head": "Room rent collected", "amount": _sum(db, Payment.rent_amount, Payment.month.like(prefix), *hall)},
        {"head": "Amenity charges collected",
         "amount": _sum(db, Payment.amenity_amount, Payment.month.like(prefix), *hall)},
        {"head": "Mess charges collected", "amount": _sum(db, Payment.mess_amount, Payment.month.like(prefix), *hall)},
    ]

    exp_where = [Expenditure.year == year] + ([Expenditure.hostel_id == hostel_id] if hostel_id else [])
    sal_where = [Salary.month.like(prefix)] + ([TemporaryStaff.hostel_id == hostel_id] if hostel_id else [])
    chq_where = [MessManagerCheque.month.like(prefix)] + (
        [MessManagerCheque.hostel_id == hostel_id] if hostel_id else [])
    salaries = float(db.scalar(
        select(func.coalesce(func.sum(Salary.amount_payable), 0)).join(TemporaryStaff).where(*sal_where)))

    expenditure = [
        {"head": "Hall expenditure (upkeep, gardens, etc.)", "amount": _sum(db, Expenditure.amount, *exp_where)},
        {"head": "Staff salaries", "amount": salaries},
        {"head": "Paid to mess managers", "amount": _sum(db, MessManagerCheque.amount, *chq_where)},
    ]
    if not hostel_id:
        expenditure.append({"head": "SAC petty expenses", "amount": _sum(
            db, PettyExpense.amount, func.extract("year", PettyExpense.spent_on) == year)})

    total_in = round(sum(i["amount"] for i in income), 2)
    total_out = round(sum(e["amount"] for e in expenditure), 2)
    return {
        "year": year, "scope": scope, "income": income, "expenditure": expenditure,
        "total_income": total_in, "total_expenditure": total_out, "balance": round(total_in - total_out, 2),
        "generated_at": datetime.utcnow(),
    }
