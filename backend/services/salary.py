import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Leave, Salary, TemporaryStaff


def month_bounds(month: str) -> tuple[date, date]:
    year, mon = map(int, month.split("-"))
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def leave_days_in_month(leaves: list[Leave], first: date, last: date) -> int:
    days = 0
    for leave in leaves:
        start, end = max(leave.start_date, first), min(leave.end_date, last)
        if start <= end:
            days += (end - start).days + 1
    return days


def _row(staff: TemporaryStaff, salary: Salary) -> dict:
    return {
        "staff_id": staff.id, "name": staff.name, "role": staff.role, "month": salary.month,
        "days_worked": salary.days_worked, "daily_pay": float(staff.daily_pay),
        "amount_payable": float(salary.amount_payable), "cheque_no": salary.cheque_no,
    }


def generate_salaries(db: Session, hostel_id: int, month: str) -> list[dict]:
    """Consolidated salary list: daily pay x (days in month - leave days), one cheque per employee.
    Re-running for the same month recomputes the amounts (e.g. after a late leave entry)."""
    first, last = month_bounds(month)
    staff_list = db.scalars(
        select(TemporaryStaff).where(
            TemporaryStaff.hostel_id == hostel_id, TemporaryStaff.is_active, TemporaryStaff.joined_on <= last
        )
    ).all()
    rows = []
    for staff in staff_list:
        start = max(first, staff.joined_on)
        days = (last - start).days + 1 - leave_days_in_month(staff.leaves, start, last)
        amount = round(days * float(staff.daily_pay), 2)
        salary = db.scalar(select(Salary).where(Salary.staff_id == staff.id, Salary.month == month))
        if salary:
            salary.days_worked, salary.amount_payable = days, amount
        else:
            salary = Salary(staff_id=staff.id, month=month, days_worked=days, amount_payable=amount,
                            cheque_no=f"SAL-{month}-{staff.id}")
            db.add(salary)
        rows.append(_row(staff, salary))
    db.commit()
    return rows


def list_salaries(db: Session, hostel_id: int, month: str) -> list[dict]:
    salaries = db.scalars(
        select(Salary).join(TemporaryStaff).where(TemporaryStaff.hostel_id == hostel_id, Salary.month == month)
    ).all()
    return [_row(s.staff, s) for s in salaries]
