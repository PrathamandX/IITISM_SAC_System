from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth import check_hostel_access, require_roles
from backend.database import get_db
from backend.models import AnnualGrant, Expenditure, GrantAllocation, Hostel, PettyExpense, Role, User
from backend.schemas.finance import (
    AllocationCreate, AllocationOut, ExpenditureCreate, ExpenditureOut, GrantCreate, GrantOut, PettyExpenseCreate,
    PettyExpenseOut, Statement,
)
from backend.services.accounts import statement_of_accounts

router = APIRouter(prefix="/api", tags=["Grants, expenditure & accounts"])


@router.post("/grants", response_model=GrantOut, status_code=201)
def receive_grant(data: GrantCreate, db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman))):
    """Record the annual grant received from the Institute."""
    if db.scalar(select(AnnualGrant).where(AnnualGrant.year == data.year)):
        raise HTTPException(409, "Grant for this year is already recorded")
    grant = AnnualGrant(**data.model_dump())
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant


@router.get("/grants", response_model=list[GrantOut])
def list_grants(db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman, Role.warden))):
    return db.scalars(select(AnnualGrant).order_by(AnnualGrant.year.desc())).all()


@router.post("/grants/allocations", response_model=AllocationOut)
def allocate_grant(data: AllocationCreate, db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman))):
    """Chairman distributes the grant among halls; total allocation can never exceed the grant."""
    grant = db.scalar(select(AnnualGrant).where(AnnualGrant.year == data.year))
    if not grant:
        raise HTTPException(404, "No grant recorded for this year")
    if not db.get(Hostel, data.hostel_id):
        raise HTTPException(404, "Hostel not found")
    allocation = db.scalar(select(GrantAllocation).where(GrantAllocation.year == data.year,
                                                         GrantAllocation.hostel_id == data.hostel_id))
    others = float(db.scalar(select(func.coalesce(func.sum(GrantAllocation.amount), 0)).where(
        GrantAllocation.year == data.year, GrantAllocation.hostel_id != data.hostel_id)))
    if others + data.amount > float(grant.amount):
        raise HTTPException(400, f"Allocation exceeds the grant. Unallocated: {float(grant.amount) - others:.2f}")
    if allocation:
        allocation.amount = data.amount
    else:
        allocation = GrantAllocation(**data.model_dump())
        db.add(allocation)
    db.commit()
    db.refresh(allocation)
    return allocation


@router.get("/grants/allocations", response_model=list[AllocationOut])
def list_allocations(year: int, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(Role.chairman, Role.warden))):
    query = select(GrantAllocation).where(GrantAllocation.year == year)
    if user.role == Role.warden:
        query = query.where(GrantAllocation.hostel_id == user.hostel_id)
    return db.scalars(query).all()


@router.post("/expenditures", response_model=ExpenditureOut, status_code=201)
def enter_expenditure(data: ExpenditureCreate, db: Session = Depends(get_db),
                      user: User = Depends(require_roles(Role.warden))):
    """Warden enters expenditure against the hall's allocation; overspending is rejected."""
    check_hostel_access(user, data.hostel_id)
    allocated = db.scalar(select(GrantAllocation.amount).where(GrantAllocation.year == data.year,
                                                               GrantAllocation.hostel_id == data.hostel_id))
    if allocated is None:
        raise HTTPException(400, "No grant allocated to this hall for the year")
    spent = float(db.scalar(select(func.coalesce(func.sum(Expenditure.amount), 0)).where(
        Expenditure.year == data.year, Expenditure.hostel_id == data.hostel_id)))
    if spent + data.amount > float(allocated):
        raise HTTPException(400, f"Expenditure exceeds allocation. Remaining: {float(allocated) - spent:.2f}")
    exp = Expenditure(**data.model_dump(exclude={"spent_on"}), spent_on=data.spent_on or date.today(),
                      entered_by=user.id)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.get("/expenditures", response_model=list[ExpenditureOut])
def list_expenditures(year: int, hostel_id: int | None = None, db: Session = Depends(get_db),
                      user: User = Depends(require_roles(Role.chairman, Role.warden))):
    if user.role == Role.warden:
        hostel_id = user.hostel_id
    query = select(Expenditure).where(Expenditure.year == year)
    if hostel_id:
        query = query.where(Expenditure.hostel_id == hostel_id)
    return db.scalars(query.order_by(Expenditure.spent_on)).all()


@router.post("/petty-expenses", response_model=PettyExpenseOut, status_code=201)
def enter_petty_expense(data: PettyExpenseCreate, db: Session = Depends(get_db),
                        user: User = Depends(require_roles(Role.chairman, Role.clerk))):
    exp = PettyExpense(description=data.description, amount=data.amount,
                       spent_on=data.spent_on or date.today(), entered_by=user.id)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.get("/petty-expenses", response_model=list[PettyExpenseOut])
def list_petty_expenses(db: Session = Depends(get_db), _=Depends(require_roles(Role.chairman, Role.clerk))):
    return db.scalars(select(PettyExpense).order_by(PettyExpense.spent_on.desc())).all()


@router.get("/statement", response_model=Statement)
def statement(year: int, hostel_id: int | None = None, db: Session = Depends(get_db),
              user: User = Depends(require_roles(Role.warden, Role.chairman, Role.controlling_warden))):
    """Statement of accounts; a warden always gets their own hall's statement."""
    if user.role == Role.warden:
        hostel_id = user.hostel_id
    if hostel_id and not db.get(Hostel, hostel_id):
        raise HTTPException(404, "Hostel not found")
    return statement_of_accounts(db, year, hostel_id)
