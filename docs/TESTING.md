# Testing Guide

## 1. How to run

```bash
cd project
pip install -r requirements.txt
pytest                     # run everything (≈25 s)
pytest -v                  # one line per test case
pytest tests/test_billing.py              # one module
pytest tests/test_billing.py::test_dues_formula   # one test
pytest -k "salary"         # tests whose name contains "salary"
pytest --cov=backend --cov=main --cov-report=term-missing   # coverage report
pytest --cov=backend --cov-report=html    # HTML report in htmlcov/index.html
```

**No PostgreSQL is needed for testing.** `tests/conftest.py` points `DATABASE_URL` at a temporary SQLite file (`tests/test.db`, deleted after the run) *before* the app is imported. The same SQLAlchemy models and business logic run as in production.

**Current result: 132 passed, 99% line coverage** (1154 statements, 7 missed; the missed lines are defensive branches such as a missing `.env` variable).

## 2. Test design

| Technique | How it is applied |
|---|---|
| **Isolation** | The `client` fixture drops and recreates every table before each test, so tests never depend on one another's order |
| **Fixture "world"** | Seeds a realistic campus: 2 hostels (Jasper, Amber), 3 rooms, a clerk, warden and mess manager per hostel, a dean, the chairman and one admitted student |
| **Equivalence partitioning** | Valid vs invalid classes for every input (month, money, phone, roll no, role, dates) |
| **Boundary value analysis** | Exactly-equal limits pass, and one unit over fails: allocation = remaining grant; expenditure = remaining allocation; 2 MB + 1 byte photo; leap-year February; mid-month joiners; leaves crossing month ends |
| **Authorization matrix** | Each protected action is tried by every role that must be denied (403) and by the "other hostel" user (403) |
| **State-transition testing** | Dues: *pending → paid → locked*; complaint: *open → (ATR) → resolved*; staff: *active → left*; cheque: *issued → signed* |
| **End-to-end / scenario** | `test_workflow.py` follows the activity diagram from admission to audit |
| **Security** | Expired, forged, malformed and revoked JWTs; client-supplied amounts are ignored; file type and size checks; CORS origin allow-list |
| **Parametrization** | `@pytest.mark.parametrize` runs one test body over many invalid inputs |

## 3. Test case catalogue

`✔` = expected success. Codes are the expected HTTP status.

### 3.1 Authentication & users (`test_auth.py`, 24 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| AU-01 | test_login_success_returns_token_and_role | Correct chairman credentials | 200, bearer token + role |
| AU-02..04 | test_login_rejects_bad_credentials | Wrong password / unknown user / empty | 401 / 401 / 422 |
| AU-05 | test_me_returns_current_user | `/me` with a token | Profile, no password hash |
| AU-06..08 | test_protected_endpoint_requires_valid_token | No token / garbage token / Basic auth | 401 |
| AU-09 | test_expired_token_rejected | Token with `exp` in the past | 401 |
| AU-10 | test_token_signed_with_other_secret_rejected | Forged signature | 401 |
| AU-11 | test_token_for_nonexistent_user_rejected | Valid signature, unknown user id | 401 |
| AU-12 | test_change_password | Wrong old password; short new one; success; old password stops working | 400, 422, 204, 401 |
| AU-13..20 | test_create_user_validation | Student role; warden without hostel; unknown hostel; bad username chars; short username; short password; unknown role; duplicate username | 400, 400, 400, 422, 422, 422, 422, 409 |
| AU-21 | test_only_chairman_manages_users | Warden, clerk, dean, student create/list users | 403 |
| AU-22 | test_user_list_excludes_students | List users | 8 staff, no students |
| AU-23 | test_deactivated_user_cannot_login_or_use_token | Deactivate, then use old token and login | 401, 401 |
| AU-24 | test_chairman_cannot_deactivate_self_or_missing_user | Self / id 9999 | 400 / 404 |

### 3.2 Hostels, rooms, occupancy (`test_hostels.py`, 13 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| HO-01 | test_create_and_list_hostels | Student lists hostels | Sorted names |
| HO-02..06 | test_create_hostel_validation | Duplicate name; empty name; negative charge; missing field; non-numeric | 409, 422 ×4 |
| HO-07 | test_only_chairman_creates_hostels_and_rooms | 4 other roles | 403 |
| HO-08 | test_update_hostel | Change amenity; unknown id | 200, 404 |
| HO-09 | test_room_rules | Duplicate room; unknown hostel; empty room no.; same number in another hostel | 409, 404, 422, 201 |
| HO-10 | test_list_rooms_and_vacant_filter | All rooms, vacant only, other-hostel clerk, student | occupancy flags, `["102"]`, 403, 403 |
| HO-11 | test_hostel_occupancy | Own warden; other warden; unknown | exact counts, 403, 404 |
| HO-12 | test_overall_occupancy_updates_after_admission | Dean before and after an admission | 3/1/2, then 2 occupied |
| HO-13 | test_overall_occupancy_restricted | Warden, clerk, student, mess manager | 403 |

### 3.3 Admission & students (`test_students.py`, 22 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| ST-01 | test_admission_auto_allots_first_vacant_room | No room given | Room 102 (101 taken) |
| ST-02 | test_admission_to_a_chosen_room | Specific room | That room |
| ST-03 | test_admission_room_rules | Room of other hostel; occupied room; unknown room; last room; hostel full; unknown hostel | 400, 409, 400, 201, 409, 404 |
| ST-04 | test_admission_duplicate_roll_number | Same roll twice | 409 |
| ST-05..12 | test_admission_field_validation | Bad phone ×2, roll with space, short roll, empty name, short address, weak password, empty admission note | 422 |
| ST-13 | test_admission_authorization | Other-hostel clerk; warden, mess mgr, dean, student | 403 |
| ST-14 | test_admitted_student_can_login_and_see_profile | Student `/me`; clerk `/students/me` | Profile, 403 |
| ST-15 | test_allotment_letter | Letter content | Hostel, room, rent, amenity, letter no. |
| ST-16 | test_allotment_letter_access | Another student's letter; other-hostel clerk; unknown roll | 403, 403, 404 |
| ST-17 | test_student_list_is_scoped | Clerk1/clerk2/chairman; clerk tries `?hostel_id=` of another hostel | Own hostel only; parameter ignored |
| ST-18 | test_photo_upload | PNG by the student | Stored and served |
| ST-19..21 | test_photo_upload_rejections | .exe; GIF; 2 MB + 1 byte | 400 |
| ST-22 | test_photo_upload_access | Student uploads for another student; warden | 403 |

### 3.4 Billing, payments, mess sheet (`test_billing.py`, 27 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| BI-01 | test_dues_formula | 3000 mess + 500 amenity + 1500 rent | total 5000, unpaid |
| BI-02 | test_dues_without_mess_charge_is_rent_plus_amenity | No mess charge yet | 2000 |
| BI-03 | test_payment_is_computed_server_side_and_only_once | Pay decimals; pay again | 4750.50; 409 |
| BI-04 | test_payment_ignores_client_supplied_amount | Client sends `total: 1` | Charged 5000 |
| BI-05 | test_cannot_pay_before_mess_charges_entered | Pay with no mess charge | 400 |
| BI-06 | test_clerk_can_record_counter_payment | Clerk pays for the student | 201 |
| BI-07 | test_mess_charge_can_be_corrected_until_paid | Update, pay, update again | 201, 201, 409 |
| BI-08..13 | test_invalid_month_rejected | `2026-13`, `2026-9`, `26-09`, `2026/09`, `abcd-ef`, empty | 422 |
| BI-14..17 | test_invalid_mess_amount_rejected | -1, text, null, > 10 million | 422 |
| BI-18 | test_zero_mess_charge_allowed_but_not_payable | Charge 0 | Saved; payment 400 |
| BI-19 | test_mess_charge_authorization | Other mess manager; clerk, warden, student, chairman | 403 |
| BI-20 | test_unknown_student_or_no_room | Unknown roll | 404 |
| BI-21 | test_student_cannot_see_or_pay_others_dues | View or pay a classmate's dues | 403 |
| BI-22 | test_payments_list_scoping | Student / clerk / chairman / other month | 1 / 1 / 2 / 0 |
| BI-23 | test_mess_charge_list_scoping | Own vs other mess manager; student | 1, 0, 403 |
| BI-24 | test_mess_sheet_only_counts_collected_money | Two charged, one paid | Sheet shows 3000 (paid only) |
| BI-25 | test_mess_cheque_lifecycle | Nothing collected; clerk issues; issue; duplicate; sign; unknown cheque | 400, 403, 201, 409, signed, 404 |
| BI-26 | test_mess_cheque_requires_mess_manager_account | Hostel with no mess manager | 400 |
| BI-27 | test_mess_sheet_access | Student, warden, mess manager, dean | 403 |

### 3.5 Complaints (`test_complaints.py`, 12 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| CO-01 | test_raise_repair_and_behavior_complaints | Both types | 201, status open |
| CO-02..06 | test_complaint_validation | Repair without repair_type; behavior without against; short description; unknown type; > 2000 chars | 422 |
| CO-07 | test_only_students_raise_complaints | Warden, clerk, chairman | 403 |
| CO-08 | test_complaint_visibility | Student / warden / other clerk / dean / chairman / mess manager | 1 / 1 / 1 / 2 / 2 / 403 |
| CO-09 | test_warden_posts_atr_and_resolves | ATR with resolve | resolved, visible to student |
| CO-10 | test_atr_without_resolving_keeps_complaint_open | `resolve=false` | Still open |
| CO-11 | test_atr_rules | Other warden, clerk, student; ATR too short; unknown complaint | 403 ×3, 422, 404 |
| CO-12 | test_status_filter | open / resolved / invalid status | 1, 1, 422 |

### 3.6 Staff, leave, salary (`test_staff.py`, 18 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| SF-01 | test_recruit_and_list_staff | Recruit, then warden lists | Active, listed |
| SF-02 | test_joined_on_defaults_to_today | No joining date | Defaults to today |
| SF-03..07 | test_recruit_validation | Role "cook"; negative pay; bad phone; empty name; bad date | 422 |
| SF-08 | test_staff_authorization | Other-hostel clerk; student; mess manager; unknown hostel; list other hostel | 403, 403, 403, 404, 403 |
| SF-09 | test_remove_staff_keeps_history | Other clerk removes; own clerk removes; list; include_inactive; salary history; unknown id | 403, 204, [], 1, 1, 404 |
| SF-10 | test_leave_rules | Valid; overlapping; end before start; unknown staff; warden enters; other clerk | 201, 409, 422, 404, 403, 403 |
| SF-11 | test_no_leave_for_departed_staff | Leave after removal | 400 |
| SF-12 | test_salary_full_month | September, no leave | 30 days × 400 = 12000 |
| SF-13 | test_salary_deducts_leave_including_leave_spanning_months | Leave 30 Aug–2 Sep plus 15 Sep | 27 days = 10800 |
| SF-14 | test_salary_for_staff_joining_mid_month | Joined 21 Sep | 10 days |
| SF-15 | test_salary_excludes_future_joiners_and_departed_staff | Joins in October; has left | Empty list |
| SF-16 | test_salary_february_leap_year | Feb 2028 | 29 days |
| SF-17 | test_regenerating_salary_recomputes_without_new_cheque | Late leave, then regenerate | 25 days, same cheque no. |
| SF-18 | test_salary_authorization_and_validation | Warden generates; other clerk; month 00; student lists | 403, 403, 422, 403 |

### 3.7 Grants, expenditure, accounts (`test_finance.py`, 12 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| FI-01 | test_grant_rules | Duplicate year; year 1999; negative; warden records | 409, 422, 422, 403 |
| FI-02 | test_allocation_cannot_exceed_grant | No grant; 60k; 40,001 over; exactly 40k; unknown hostel | 404, 200, 400, 200, 404 |
| FI-03 | test_reallocation_replaces_previous_amount | 90k then 30k for the same hall frees 60k | Amounts [30k, 70k] |
| FI-04 | test_only_chairman_allocates | Warden, clerk, dean | 403 |
| FI-05 | test_expenditure_limited_by_allocation | No allocation; 6000; 4001 over; exactly 4000; 0.01 over | 400, 201, 400, 201, 400 |
| FI-06 | test_expenditure_authorization_and_validation | Other warden; clerk; chairman; negative; year 2201 | 403 ×3, 422 ×2 |
| FI-07 | test_expenditure_listing | Warden vs chairman | 1 vs 2 |
| FI-08 | test_petty_expenses | Chairman and clerk add; short description; negative; warden | 201, 201, 422, 422, 403 |
| FI-09 | test_hall_statement_of_accounts | A full year of money movement | Every head matches; balance 45000 |
| FI-10 | test_sac_statement_includes_petty_expenses | SAC-wide statement | Income 105000, petty 250 |
| FI-11 | test_statement_for_a_year_without_activity_is_zero | Empty year | All zeros |
| FI-12 | test_statement_access | Warden asks for another hall; chairman picks a hall; unknown hall; student, clerk, mess mgr; missing year | Own hall, Amber, 404, 403, 422 |

### 3.8 Workflow, pages, CORS (`test_workflow.py`, 4 cases)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| WF-01 | test_pages_and_health | `/`, `/dashboard`, static files, health, OpenAPI, unknown API | 200s, 404 |
| WF-02 | test_cors_allows_configured_origin_only | Preflight from allowed vs foreign origin | Header present vs absent |
| WF-03 | test_student_lifecycle | Admission → billing → payment → complaint → ATR → grant → statement | Totals consistent |
| WF-04 | test_new_chairman_account_can_manage | Second chairman account | Can create a hostel |

## 4. Traceability: requirements → tests

| Requirement (problem statement) | Tests |
|---|---|
| Admission details, photo, hostel & room allotment, letter | ST-01…22, HO-10…12 |
| Monthly mess charges entered by the mess manager | BI-07…19, BI-23 |
| Fixed room rent / amenity charge | HO-02…09, BI-01…02 |
| Total due = mess + amenity + rent | BI-01…06, WF-03 |
| Mess money to mess managers: sheet, cheque, signature | BI-24…27 |
| Complaints via browser (repair / behavior) | CO-01…08 |
| Warden views complaints, posts ATR | CO-09…12 |
| Annual grant distributed among halls; warden expenditure | FI-01…07 |
| Controlling warden overall occupancy; warden hostel occupancy | HO-11…13 |
| Staff recruit / leave; leave entry; monthly salary + cheques | SF-01…18 |
| Petty expenses | FI-08, FI-10 |
| Statement of accounts, annual consolidated print | FI-09…12 |
| Security against fraud | AU-01…24, BI-04, BI-07, BI-21, FI-02, FI-05, ST-19…22, WF-02 |

## 5. Manual UI test checklist

Run `fastapi dev main.py` and open http://127.0.0.1:8000.

| # | Log in as | Steps | Expected |
|---|---|---|---|
| 1 | chairman | Hostels & rooms → add hostel, add 2 rooms | Rooms listed as vacant |
| 2 | chairman | Users → create a clerk, warden and mess manager for the hostel | Appear in "All accounts" |
| 3 | clerk | Admit student → submit | Allotment letter shown; Print works |
| 4 | mess manager | Mess charges → enter for the student | Saved |
| 5 | student (roll no) | Dues & payment → View, then Pay | Total = mess + amenity + rent; second Pay shows an error |
| 6 | student | Complaints → raise a repair complaint | Listed as open |
| 7 | warden | Complaints → Post ATR → confirm resolve | Status becomes resolved |
| 8 | clerk | Hostel staff → recruit; Leave & salary → leave, generate | Salary list with a signature column |
| 9 | chairman | Grants → record, distribute; Mess manager sheet → issue cheque, mark signed | Limits enforced |
| 10 | warden | Hall expenditure; Statement of accounts → Print | Printable statement with signature line |
| 11 | any | Log out; open `/dashboard` directly | Redirected to login |

## 6. Adding a new test

```python
# tests/test_something.py
from tests.conftest import ok

def test_my_rule(world):                       # `world` gives you the seeded campus
    res = world.client.get("/api/hostels", headers=world.clerk1)
    assert ok(res)[0]["name"] == "Amber"
```
Available in `world`: `client`, `admin`, `jasper`, `amber`, `rooms`, `student`, `clerk1`, `warden1`, `mess1`, `clerk2`, `warden2`, `mess2`, `dean` (each user entry holds ready-made auth headers).
