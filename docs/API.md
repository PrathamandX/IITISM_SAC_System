# API Reference: SAC Hostel Management System

Base URL: `http://127.0.0.1:8000`. Interactive docs are generated from the code at **`/docs`** (Swagger UI) and **`/redoc`**. The OpenAPI schema is at `/openapi.json`.

## Conventions

| Item | Rule |
|---|---|
| Format | JSON request and response bodies (`Content-Type: application/json`), except `login` (form data) and `photo` (multipart) |
| Auth | `Authorization: Bearer <access_token>` on every `/api/*` endpoint except `login` and `health` |
| Month | `YYYY-MM`, with the month between 01 and 12 (e.g. `2026-09`). `2026-9` and `2026-13` are rejected |
| Money | Number, `0 ≤ amount ≤ 10,000,000`, rounded to 2 decimals |
| Year | Integer between 2000 and 2100 |
| Dates | ISO `YYYY-MM-DD` |

### Roles

| Role | Actor in use case diagram | Hostel-scoped? |
|---|---|---|
| `chairman` | SAC Chairman (administrator) | No |
| `controlling_warden` | Hostel Dean / controlling warden | No |
| `warden` | Hostel Warden | **Yes** |
| `clerk` | Hostel manager / caretaker / clerk | **Yes** |
| `mess_manager` | Mess Manager | **Yes** |
| `student` | Student | Own records only |

A **hostel-scoped** user can only read or change data of the hostel on their account (`hostel_id`). Requests for any other hostel return `403`.

### Error format

```json
{ "detail": "You can only access your own hostel" }
```
Validation errors (`422`) return a list with the location and reason for each problem:
```json
{ "detail": [ { "loc": ["body", "month"], "msg": "String should match pattern '^\\d{4}-(0[1-9]|1[0-2])$'", "type": "string_pattern_mismatch" } ] }
```

| Code | Meaning |
|---|---|
| 200 / 201 / 204 | OK / Created / No content |
| 400 | Business rule violated (e.g. over-spending, no room left, paying before mess charge) |
| 401 | Missing, invalid, expired or revoked token, or wrong username/password |
| 403 | Logged in but role or hostel not allowed |
| 404 | Referenced record does not exist |
| 409 | Conflict / duplicate (e.g. already paid, username taken, overlapping leave) |
| 422 | Request body or query failed validation |

---

## 1. Authentication & users (`backend/routers/auth.py`)

### POST `/api/auth/login` (public)
Form fields `username`, `password` (OAuth2 password flow). Students log in with their **roll number**.
```bash
curl -X POST localhost:8000/api/auth/login -d "username=chairman&password=Admin@123"
```
**200**
```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer", "role": "chairman", "full_name": "SAC Chairman" }
```
**401** if the credentials are wrong or the account is deactivated. The token expires after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).

### GET `/api/auth/me` (any role)
Returns the logged-in user: `{id, username, full_name, role, hostel_id, student_id, is_active}`.

### POST `/api/auth/change-password` (any role)
Body `{"old_password": "...", "new_password": "min 8 chars"}`. Returns **204**, or **400** if the old password is wrong.

### POST `/api/users` (chairman)
Creates a staff account.
```json
{ "username": "warden1", "full_name": "Dr. Rao", "password": "Passw0rd!", "role": "warden", "hostel_id": 1 }
```
Rules: username 3–50 chars `[A-Za-z0-9_.-]` and unique (**409**); password 8–72 chars. `role=student` returns **400** because students are created at admission. `warden`, `clerk` and `mess_manager` need an existing `hostel_id` (**400**).

### GET `/api/users` (chairman)
Lists all non-student accounts.

### PATCH `/api/users/{id}/deactivate` (chairman)
Deactivates an account, which blocks both login and existing tokens. **400** when you try to deactivate yourself; **404** if the account is unknown.

---

## 2. Hostels, rooms & occupancy (`backend/routers/hostels.py`)

| Method & path | Roles | Body / query | Notes |
|---|---|---|---|
| POST `/api/hostels` | chairman | `{name, amenity_charge}` | 409 if the name exists |
| GET `/api/hostels` | any | | Sorted by name |
| PUT `/api/hostels/{id}` | chairman | `{name, amenity_charge}` | 404 if unknown |
| POST `/api/hostels/{id}/rooms` | chairman | `{room_no, rent}` | 409 if the room number is duplicated within the hostel |
| GET `/api/hostels/{id}/rooms` | chairman, dean, warden, clerk | `?vacant_only=true` | Each room has `is_occupied` |
| GET `/api/hostels/{id}/occupancy` | chairman, dean, warden, clerk | | Warden: own hostel |
| GET `/api/occupancy` | controlling_warden, chairman | | Overall occupancy plus a per-hostel breakdown |

Example: `GET /api/occupancy`
```json
{ "total_rooms": 3, "occupied": 1, "vacant": 2,
  "hostels": [ { "hostel_id": 2, "hostel": "Amber", "total_rooms": 1, "occupied": 0, "vacant": 1 },
               { "hostel_id": 1, "hostel": "Jasper", "total_rooms": 2, "occupied": 1, "vacant": 1 } ] }
```

---

## 3. Students & admission (`backend/routers/students.py`)

### POST `/api/students` (clerk of that hostel, chairman)
Registers an admitted student, allots a room and creates the student's login.
```json
{ "roll_no": "21JE0001", "name": "Asha", "address": "Dhanbad, Jharkhand", "phone": "9876543210",
  "admission_note_ref": "ADM/2026/1", "hostel_id": 1, "room_id": null, "password": "Passw0rd!" }
```
- If `room_id` is omitted, the **first vacant room** in the hostel is allotted.
- **400**: the room is not in that hostel or does not exist. **404**: the hostel is unknown.
- **409**: the roll number already exists, the chosen room is occupied, or the hostel has no vacant room.
- **422**: roll number not alphanumeric or shorter than 3 chars, phone not 7–20 digits, weak password, etc.

**201** returns `StudentOut`: `{id, roll_no, name, address, phone, photo_path, admission_date, room_id}`.

### GET `/api/students` (chairman, dean, warden, clerk, mess_manager)
Optional `?hostel_id=`. Hostel-scoped roles always get their own hostel, whatever they pass.

### GET `/api/students/me` (student)

### GET `/api/students/{roll_no}/allotment-letter` (student: self; staff: own hostel)
```json
{ "letter_no": "SAC/ALLOT/2026/00001", "issued_on": "2026-09-29", "roll_no": "21JE0001", "name": "Asha",
  "address": "Dhanbad", "hostel": "Jasper", "room_no": "101", "monthly_rent": 1500.0, "monthly_amenity_charge": 500.0 }
```

### POST `/api/students/{roll_no}/photo` (student: self, clerk, chairman)
Multipart field `photo`. Accepts JPEG or PNG up to **2 MB** (anything else returns **400**). The file is stored under a random name and served at `/static/uploads/<name>`.
```bash
curl -X POST localhost:8000/api/students/21JE0001/photo -H "$H" -F "photo=@me.jpg;type=image/jpeg"
```

---

## 4. Mess charges, dues & payments (`backend/routers/billing.py`)

### POST `/api/mess-charges` (mess_manager of the student's hostel)
`{"roll_no": "21JE0001", "month": "2026-09", "amount": 3000}`. If a charge already exists for that month it is **updated**, but only until the month is paid; after payment the charge is locked (**409**).

### GET `/api/mess-charges?month=YYYY-MM` (mess_manager, clerk, warden, chairman)

### GET `/api/dues?roll_no=&month=` (student: self, clerk, warden, chairman)
**Business rule: total due = mess charge + amenity charge (hostel) + room rent (room).**
```json
{ "roll_no": "21JE0001", "month": "2026-09", "mess_charge": 3000.0, "amenity_charge": 500.0,
  "room_rent": 1500.0, "total_due": 5000.0, "paid": false }
```

### POST `/api/payments` (student: self, clerk: own hostel)
`{"roll_no": "21JE0001", "month": "2026-09"}`. **The client never sends an amount**: the server computes it (anti-fraud). Any extra field such as `total` is ignored.
- **400**: the mess charge for the month has not been entered yet. **409**: already paid.
- **201** returns `{id, student_id, month, total, paid_at}`.

### GET `/api/payments?month=` (student: own; clerk, warden: own hostel; chairman, dean: all)

### GET `/api/mess-sheet?month=` (chairman, clerk)
The printable sheet of **mess money collected** (paid dues only) for each hostel's mess manager, with a signature column.
```json
[ { "hostel_id": 1, "hostel": "Jasper", "mess_manager": "Mess1", "amount_due": 3000.0, "cheque_no": null, "signed": false } ]
```

### POST `/api/mess-sheet/cheques` (chairman)
`{"hostel_id": 1, "month": "2026-09"}` issues cheque `MESS-2026-09-1` for the collected amount.
**400**: the hostel has no mess manager, or nothing was collected. **409**: a cheque was already issued for that hostel and month.

### POST `/api/mess-sheet/cheques/{id}/sign` (chairman)
Records that the mess manager signed the sheet on receiving the cheque.

### GET `/api/mess-sheet/cheques?month=` (chairman, clerk)

---

## 5. Complaints & ATR (`backend/routers/complaints.py`)

### POST `/api/complaints` (student with an allotted room)
```json
{ "type": "repair", "repair_type": "fused light", "description": "Tube light in room 101 is fused" }
{ "type": "behavior", "against": "mess staff", "description": "Rude behaviour at dinner" }
```
`repair` needs `repair_type`; `behavior` needs `against`. The description must be 5–2000 chars (**422** otherwise).

### GET `/api/complaints?status=open|resolved`
The student sees their own complaints; warden and clerk see their hostel's; chairman and dean see all. Mess manager gets **403**.

### POST `/api/complaints/{id}/atr` (warden of that hostel)
`{"atr": "Electrician replaced the tube light", "resolve": true}` saves the Action Taken Report. With `resolve=true` (the default) it sets `status=resolved` and `resolved_at`; with `resolve=false` the complaint stays open.

---

## 6. Staff, leave & salary (`backend/routers/staff.py`)

| Method & path | Roles | Body / query |
|---|---|---|
| POST `/api/staff` | clerk, warden (own hostel), chairman | `{hostel_id, name, address, phone, role: attendant\|gardener, daily_pay, joined_on?}` |
| GET `/api/staff` | clerk, warden, chairman | `?hostel_id=&include_inactive=` |
| DELETE `/api/staff/{id}` | clerk, warden, chairman | Staff has left. The record is **deactivated, not erased**, so salary history stays auditable |
| POST `/api/leaves` | clerk, chairman | `{staff_id, start_date, end_date}`. **422** if end is before start; **409** if it overlaps another leave; **400** if the staff member has left |
| GET `/api/leaves?staff_id=` | clerk, warden, chairman | |
| POST `/api/salaries/generate` | clerk, chairman | `{hostel_id, month}` |
| GET `/api/salaries?month=&hostel_id=` | clerk, warden, chairman | |

**Salary rule:** `days_worked = days in month counted from max(1st, joined_on) − leave days inside that month`, and `amount = days_worked × daily_pay`. Leaves that span two months are split correctly. Staff who join after the month, or who have left, are excluded. Re-running for the same month **recomputes** the amounts (e.g. after a late leave entry) and keeps the same cheque number `SAL-YYYY-MM-<staff_id>`.

```json
[ { "staff_id": 1, "name": "Ramesh", "role": "attendant", "month": "2026-09", "days_worked": 27,
    "daily_pay": 400.0, "amount_payable": 10800.0, "cheque_no": "SAL-2026-09-1" } ]
```

---

## 7. Grants, expenditure & accounts (`backend/routers/finance.py`)

| Method & path | Roles | Rule |
|---|---|---|
| POST `/api/grants` `{year, amount}` | chairman | One grant per year (**409**) |
| GET `/api/grants` | chairman, warden | |
| POST `/api/grants/allocations` `{year, hostel_id, amount}` | chairman | **Sum of allocations ≤ grant** (**400**, and the message shows the unallocated balance). Re-posting for the same hall replaces its amount. **404** if there is no grant for the year |
| GET `/api/grants/allocations?year=` | chairman, warden (own) | |
| POST `/api/expenditures` `{hostel_id, year, category, description, amount, spent_on?}` | warden (own hall) | **Sum of expenditure ≤ the hall's allocation** (**400** shows the remaining amount; **400** if nothing is allocated) |
| GET `/api/expenditures?year=&hostel_id=` | chairman, warden (own) | |
| POST `/api/petty-expenses` `{description, amount, spent_on?}` | chairman, clerk | Newspapers, magazines, small repairs |
| GET `/api/petty-expenses` | chairman, clerk | |
| GET `/api/statement?year=&hostel_id=` | warden (always own hall), chairman, dean | Annual consolidated statement |

**Statement of accounts**

| Income | Expenditure |
|---|---|
| Institute grant (the hall's allocation, or the whole grant for SAC) | Hall expenditure |
| Room rent collected | Staff salaries |
| Amenity charges collected | Paid to mess managers (cheques) |
| Mess charges collected | SAC petty expenses (SAC-wide statement only) |

```json
{ "year": 2026, "scope": "Jasper",
  "income": [ {"head": "Institute grant", "amount": 60000.0}, {"head": "Room rent collected", "amount": 1500.0},
              {"head": "Amenity charges collected", "amount": 500.0}, {"head": "Mess charges collected", "amount": 3000.0} ],
  "expenditure": [ {"head": "Hall expenditure (upkeep, gardens, etc.)", "amount": 5000.0},
                   {"head": "Staff salaries", "amount": 12000.0}, {"head": "Paid to mess managers", "amount": 3000.0} ],
  "total_income": 65000.0, "total_expenditure": 20000.0, "balance": 45000.0, "generated_at": "2026-09-29T10:00:00" }
```

---

## 8. Other

| Path | Purpose |
|---|---|
| GET `/api/health` | `{"status": "ok"}` liveness check (public) |
| GET `/` | Login page |
| GET `/dashboard` | Role-based dashboard (loads data with the stored JWT) |
| `/static/*` | CSS, JS and uploaded photos |

## 9. Endpoint × role matrix

| Endpoint group | chairman | controlling_warden | warden | clerk | mess_manager | student |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Users | ✔ | | | | | |
| Create hostel/room | ✔ | | | | | |
| View rooms / hostel occupancy | ✔ | ✔ | own | own | | |
| Overall occupancy | ✔ | ✔ | | | | |
| Admit student | ✔ | | | own | | |
| Allotment letter | ✔ | ✔ | own | own | own | self |
| Enter mess charge | | | | | own | |
| View dues | ✔ | | own | own | | self |
| Pay dues | | | | own | | self |
| Mess sheet / cheques | ✔ (issue, sign) | | | view | | |
| Raise complaint | | | | | | ✔ |
| View complaints | ✔ | ✔ | own | own | | self |
| Post ATR | | | own | | | |
| Staff / salaries | ✔ | | own | own | | |
| Enter leave, generate salary | ✔ | | | own | | |
| Grants & allocations | ✔ | | view own | | | |
| Hall expenditure | view | | own | | | |
| Petty expenses | ✔ | | | ✔ | | |
| Statement of accounts | ✔ | ✔ | own | | | |
