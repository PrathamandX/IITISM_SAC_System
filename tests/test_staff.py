"""Temporary staff (attendants, gardeners), leave and monthly salary."""
import pytest

from tests.conftest import MONTH, ok


def recruit(w, who=None, hostel=None, **extra):
    body = {"hostel_id": (hostel or w.jasper)["id"], "name": "Ramesh", "address": "Dhanbad", "phone": "9000000000",
            "role": "attendant", "daily_pay": 400, "joined_on": "2026-01-01", **extra}
    return w.client.post("/api/staff", json=body, headers=who or w.clerk1)


def leave(w, staff_id, start, end, who=None):
    return w.client.post("/api/leaves", json={"staff_id": staff_id, "start_date": start, "end_date": end},
                         headers=who or w.clerk1)


def salaries(w, month=MONTH, who=None):
    return w.client.post("/api/salaries/generate", json={"hostel_id": w.jasper["id"], "month": month},
                         headers=who or w.clerk1)


def test_recruit_and_list_staff(world):
    s = ok(recruit(world), 201)
    assert s["is_active"] and s["daily_pay"] == 400
    assert [x["name"] for x in ok(world.client.get("/api/staff", headers=world.warden1))] == ["Ramesh"]


def test_joined_on_defaults_to_today(world):
    body = {"hostel_id": world.jasper["id"], "name": "Sita", "address": "Dhanbad", "phone": "9000000001",
            "role": "gardener", "daily_pay": 350}
    assert ok(world.client.post("/api/staff", json=body, headers=world.clerk1), 201)["joined_on"]


@pytest.mark.parametrize("extra", [{"role": "cook"}, {"daily_pay": -5}, {"phone": "call me"}, {"name": ""},
                                   {"joined_on": "yesterday"}])
def test_recruit_validation(world, extra):
    assert recruit(world, **extra).status_code == 422


def test_staff_authorization(world):
    assert recruit(world, who=world.clerk2).status_code == 403            # other hostel
    assert recruit(world, who=world.student).status_code == 403
    assert recruit(world, who=world.mess1).status_code == 403
    assert recruit(world, who=world.admin, hostel={"id": 9999}).status_code == 404
    assert world.client.get(f"/api/staff?hostel_id={world.jasper['id']}", headers=world.clerk2).status_code == 403


def test_remove_staff_keeps_history(world):
    c = world.client
    s = ok(recruit(world), 201)
    ok(salaries(world))
    assert c.delete(f"/api/staff/{s['id']}", headers=world.clerk2).status_code == 403
    assert c.delete(f"/api/staff/{s['id']}", headers=world.clerk1).status_code == 204
    assert ok(c.get("/api/staff", headers=world.clerk1)) == []
    assert len(ok(c.get("/api/staff?include_inactive=true", headers=world.clerk1))) == 1
    assert len(ok(c.get(f"/api/salaries?month={MONTH}", headers=world.clerk1))) == 1   # old salary still auditable
    assert c.delete("/api/staff/9999", headers=world.clerk1).status_code == 404


def test_leave_rules(world):
    sid = ok(recruit(world), 201)["id"]
    ok(leave(world, sid, "2026-09-10", "2026-09-12"), 201)
    assert leave(world, sid, "2026-09-12", "2026-09-15").status_code == 409     # overlaps
    assert leave(world, sid, "2026-09-05", "2026-09-04").status_code == 422     # end before start
    assert leave(world, 9999, "2026-09-01", "2026-09-01").status_code == 404
    assert leave(world, sid, "2026-09-20", "2026-09-20", who=world.warden1).status_code == 403  # clerk enters leave
    assert leave(world, sid, "2026-09-20", "2026-09-20", who=world.clerk2).status_code == 403
    assert len(ok(world.client.get(f"/api/leaves?staff_id={sid}", headers=world.warden1))) == 1


def test_no_leave_for_departed_staff(world):
    sid = ok(recruit(world), 201)["id"]
    world.client.delete(f"/api/staff/{sid}", headers=world.clerk1)
    assert leave(world, sid, "2026-09-01", "2026-09-02").status_code == 400


def test_salary_full_month(world):
    ok(recruit(world), 201)
    row = ok(salaries(world))[0]
    assert (row["days_worked"], row["amount_payable"]) == (30, 12000)           # September has 30 days
    assert row["cheque_no"].startswith(f"SAL-{MONTH}-")


def test_salary_deducts_leave_including_leave_spanning_months(world):
    sid = ok(recruit(world), 201)["id"]
    ok(leave(world, sid, "2026-08-30", "2026-09-02"), 201)       # 2 days fall in September
    ok(leave(world, sid, "2026-09-15", "2026-09-15"), 201)       # 1 day
    row = ok(salaries(world))[0]
    assert (row["days_worked"], row["amount_payable"]) == (27, 10800)


def test_salary_for_staff_joining_mid_month(world):
    ok(recruit(world, joined_on="2026-09-21"), 201)              # 21..30 = 10 days
    assert ok(salaries(world))[0]["days_worked"] == 10


def test_salary_excludes_future_joiners_and_departed_staff(world):
    ok(recruit(world, joined_on="2026-10-05"), 201)
    gone = ok(recruit(world, name="Mohan"), 201)
    world.client.delete(f"/api/staff/{gone['id']}", headers=world.clerk1)
    assert ok(salaries(world)) == []


def test_salary_february_leap_year(world):
    ok(recruit(world), 201)
    assert ok(salaries(world, month="2028-02"))[0]["days_worked"] == 29


def test_regenerating_salary_recomputes_without_new_cheque(world):
    sid = ok(recruit(world), 201)["id"]
    first = ok(salaries(world))[0]
    ok(leave(world, sid, "2026-09-01", "2026-09-05"), 201)           # late leave entry
    second = ok(salaries(world))[0]
    assert second["days_worked"] == 25 and second["cheque_no"] == first["cheque_no"]
    assert len(ok(world.client.get(f"/api/salaries?month={MONTH}", headers=world.warden1))) == 1


def test_salary_authorization_and_validation(world):
    assert salaries(world, who=world.warden1).status_code == 403
    assert salaries(world, who=world.clerk2).status_code == 403
    assert salaries(world, month="2026-00").status_code == 422
    assert world.client.get(f"/api/salaries?month={MONTH}", headers=world.student).status_code == 403
