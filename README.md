# IIT (ISM) SAC Hostel Management System

**Software Engineering project, Problem 16 (Group 16).**
A web application that automates the book-keeping of the IIT (ISM) Students' Activity Center (SAC): student admission and room allotment, monthly mess, rent and amenity billing, complaints with Action Taken Reports, hostel staff salaries, grant distribution, petty expenses, and the annual statement of accounts for audit.

| | |
|---|---|
| **Backend** | Python 3.10+, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2 |
| **Database** | PostgreSQL (driver `psycopg2`); SQLite for automated tests |
| **Security** | JWT (PyJWT, HS256) bearer tokens, bcrypt password hashing, role-based and hostel-scoped authorization, CORS allow-list |
| **Frontend** | Jinja2 templates + vanilla JavaScript + CSS (no build step), print-ready reports |
| **Testing** | pytest + FastAPI TestClient, **132 tests, 99% coverage** |

**Documentation**
- [docs/API.md](docs/API.md): full API reference (every endpoint, request/response, errors, role matrix)
- [docs/TESTING.md](docs/TESTING.md): how to run the tests, test design, the full test-case catalogue and traceability
- [docs/diagrams/](docs/diagrams/): use case, class, activity, state and sequence diagrams
- Live Swagger UI at `/docs` once the server is running

---

## 1. Quick start

### Prerequisites
- Python 3.10 or newer
- PostgreSQL 13+ (local install **or** Docker)

### Step 1: start PostgreSQL
**Option A (Docker):**
```bash
docker run -d --name sac-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=sac_hostel -p 5432:5432 postgres:16
```
**Option B (installed PostgreSQL):** create the database. On Windows `psql` is in `C:\Program Files\PostgreSQL\<version>\bin`.
```bash
psql -U postgres -c "CREATE DATABASE sac_hostel;"
```

### Step 2: configure `.env`
Copy `.env.example` to `.env` and fill in the values:

| Variable | Meaning |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` | PostgreSQL connection |
| `DATABASE_URL` | Optional full URL that overrides the above (e.g. `sqlite:///./dev.db` for a quick demo) |
| `JWT_SECRET_KEY` | Long random secret: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Token settings (default HS256, 60 min) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | First SAC chairman account, created automatically on first start |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |

The app refuses to start if a required secret is missing. No credentials are hard-coded.

### Step 3: install and run
```bash
python -m venv venv
venv\Scripts\activate              # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
fastapi dev main.py
```
- Website: http://127.0.0.1:8000 (log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`)
- API docs: http://127.0.0.1:8000/docs

Tables are created automatically on startup.

### Step 4: first-time walkthrough
1. **Chairman** → *Hostels & rooms*: add a hostel (with its amenity charge) and rooms (with their rent).
2. **Chairman** → *Users*: create a clerk, a warden and a mess manager for that hostel, plus a controlling warden (dean).
3. **Clerk** → *Admit student*: enter the admission details. The room is allotted and the allotment letter printed.
4. **Mess manager** → *Mess charges*: enter the month's charge for the student.
5. **Student** (logs in with their roll number) → *Dues & payment*: view the total and pay; *Complaints*: raise one.
6. **Warden** → *Complaints*: post the ATR; *Hall expenditure*; *Statement of accounts* → Print.
7. **Clerk** → *Hostel staff*, *Leave & salary*: recruit, enter leave, generate the salary list and cheques.
8. **Chairman** → *Grants*: record and distribute the grant; *Mess manager sheet*: issue cheques and mark them signed.

---

## 2. Running the tests
```bash
pytest                                                     # 132 tests, about 25 s
pytest -v                                                  # verbose
pytest --cov=backend --cov=main --cov-report=term-missing  # coverage
```
Tests use a throwaway SQLite database, so PostgreSQL does not have to be running. See [docs/TESTING.md](docs/TESTING.md) for the full catalogue of test cases.

---

## 3. Requirements → implementation

| Requirement (problem statement) | Where it is implemented |
|---|---|
| Student presents admission note, name, address, phone, photograph → hostel and room allotted → letter issued | `POST /api/students`, `POST /api/students/{roll}/photo`, `GET /api/students/{roll}/allotment-letter` |
| Mess manager inputs monthly mess charges | `POST /api/mess-charges` |
| Fixed room rent per room (newer hostels higher); fixed amenity charge per hostel | `Room.rent`, `Hostel.amenity_charge` |
| Mess money handed to mess managers: printed sheet, cheques, signatures | `GET /api/mess-sheet`, `POST /api/mess-sheet/cheques`, `.../{id}/sign` |
| Total due = mess charge + amenity charge + room rent | `services/billing.py::compute_dues`, `GET /api/dues`, `POST /api/payments` |
| Complaints (repairs, staff behaviour) from a browser, 24×7 | `POST /api/complaints` |
| Annual grant, chairman distributes among halls, wardens enter expenditure | `POST /api/grants`, `/api/grants/allocations`, `/api/expenditures` |
| Controlling warden views overall occupancy | `GET /api/occupancy` |
| Warden views hostel occupancy, complaints; posts ATR | `GET /api/hostels/{id}/occupancy`, `POST /api/complaints/{id}/atr` |
| Attendants and gardeners on daily pay; clerk enters leave; monthly salary list and cheques | `/api/staff`, `/api/leaves`, `/api/salaries/generate` |
| Recruit staff with daily pay; delete when they leave | `POST /api/staff`, `DELETE /api/staff/{id}` |
| Petty expenses (repairs, newspapers, magazines) | `/api/petty-expenses` |
| Warden views and prints the annual consolidated statement for audit | `GET /api/statement` + Print |
| Very secure; prevent fraud and financial irregularities | See §5 |

### Business rules enforced by the server
1. Payment amounts are **always computed by the server**; a client-supplied amount is ignored.
2. A month's dues can be paid **only once**, and only after the mess charge is entered.
3. A mess charge can be corrected until the month is paid, then it is **locked**.
4. Each student occupies exactly one room and each room holds at most one student; the first vacant room is allotted automatically.
5. Grant allocations can never exceed the annual grant; hall expenditure can never exceed its allocation.
6. Salary = (days in the month from the joining date − leave days in that month) × daily pay. Leaves may span months and cannot overlap.
7. Only mess money actually **collected** is paid to a mess manager, with one cheque per hostel per month.
8. Financial records (payments, cheques, salaries, expenditure) have **no edit or delete endpoints**. Departed staff are deactivated so history stays auditable.

---

## 4. Architecture

```
Browser (Jinja2 page + app.js) ──HTTPS/JSON + JWT──► FastAPI routers ──► services (business rules) ──► SQLAlchemy ORM ──► PostgreSQL
```

```
project/
├── main.py                  # entry point: app, CORS, static files, routers, table creation, first admin
├── .env / .env.example      # configuration (no secrets in code)
├── requirements.txt
├── pytest.ini
├── backend/
│   ├── config.py            # loads and validates .env
│   ├── database.py          # engine, SessionLocal, Base, get_db dependency
│   ├── models/              # SQLAlchemy tables (from the class diagram)
│   │   ├── user.py          #   User, Role
│   │   ├── hostel.py        #   Hostel, Room, Student
│   │   ├── complaint.py     #   Complaint (repair / behavior), status, ATR
│   │   ├── staff.py         #   TemporaryStaff, Leave, Salary
│   │   └── finance.py       #   MessCharge, Payment, MessManagerCheque, AnnualGrant, GrantAllocation, Expenditure, PettyExpense
│   ├── schemas/             # Pydantic request/response models and validation
│   ├── routers/             # auth, hostels, students, billing, complaints, staff, finance, pages
│   ├── services/            # billing, salary, accounts (statement), occupancy
│   └── auth/                # security.py (bcrypt, JWT), deps.py (current user, role guard, hostel scope)
├── frontend/
│   ├── templates/           # base.html, login.html, dashboard.html
│   └── static/              # style.css, app.js (role-based dashboard), uploads/
├── tests/                   # 8 test modules, 132 tests
└── docs/                    # API.md, TESTING.md, diagrams/
```

### Class diagram → database tables
| Class (diagram) | Table | Notes |
|---|---|---|
| Hostel | `hostels` | `amenityCharge`; `getOccupancy()` becomes `services/occupancy.py` |
| Room | `rooms` | `roomNo`, `rent`; `isOccupied` is derived from the allotted student |
| Student (Person) | `students` + `users` | Personal details plus a login account (role `student`) |
| Warden, MessManager | `users` (role) | Hostel-scoped accounts |
| Complaint, RepairComplaint, BehaviorComplaint | `complaints` | Single-table inheritance: `type` + `repair_type` / `against` |
| TemporaryStaff (Attendant, Gardener) | `staff` | `daily_pay`, `role`, `is_active` |
| Leave, Salary | `leaves`, `salaries` | `Salary.printCheque()` becomes the cheque number + printable list |
| (billing, grants, accounts) | `mess_charges`, `payments`, `mess_manager_cheques`, `annual_grants`, `grant_allocations`, `expenditures`, `petty_expenses` | Added to support the book-keeping use cases |

---

## 5. Security
- **Authentication:** OAuth2 password flow issues a signed JWT (`sub` = user id, `role`, `exp`). Every request re-loads the user, so deactivated accounts are locked out immediately.
- **Passwords:** bcrypt with a per-user salt; minimum length 8.
- **Authorization:** `require_roles(...)` on every endpoint, plus `check_hostel_access()` so wardens, clerks and mess managers only touch their own hostel. Students only see their own records.
- **Validation:** Pydantic rejects malformed months, negative or oversized amounts, bad phone numbers and roll numbers, invalid dates and unknown enums before any business logic runs.
- **Uploads:** JPEG/PNG only, 2 MB limit, stored under random file names.
- **CORS:** only the origins listed in `CORS_ORIGINS`.
- **Audit trail:** no endpoint edits or deletes money records.

---

## 6. API at a glance
Full details are in [docs/API.md](docs/API.md).

| Area | Endpoints |
|---|---|
| Auth & users | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/change-password`, `POST/GET /api/users`, `PATCH /api/users/{id}/deactivate` |
| Hostels & rooms | `POST/GET /api/hostels`, `PUT /api/hostels/{id}`, `POST/GET /api/hostels/{id}/rooms`, `GET /api/hostels/{id}/occupancy`, `GET /api/occupancy` |
| Students | `POST/GET /api/students`, `GET /api/students/me`, `GET /api/students/{roll}/allotment-letter`, `POST /api/students/{roll}/photo` |
| Billing | `POST/GET /api/mess-charges`, `GET /api/dues`, `POST/GET /api/payments`, `GET /api/mess-sheet`, `POST/GET /api/mess-sheet/cheques`, `POST /api/mess-sheet/cheques/{id}/sign` |
| Complaints | `POST/GET /api/complaints`, `POST /api/complaints/{id}/atr` |
| Staff | `POST/GET /api/staff`, `DELETE /api/staff/{id}`, `POST/GET /api/leaves`, `POST /api/salaries/generate`, `GET /api/salaries` |
| Finance | `POST/GET /api/grants`, `POST/GET /api/grants/allocations`, `POST/GET /api/expenditures`, `POST/GET /api/petty-expenses`, `GET /api/statement` |

Quick curl session:
```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login -d "username=chairman&password=YOUR_PASSWORD" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -X POST localhost:8000/api/hostels -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"Jasper","amenity_charge":500}'
curl localhost:8000/api/occupancy -H "Authorization: Bearer $TOKEN"
```
