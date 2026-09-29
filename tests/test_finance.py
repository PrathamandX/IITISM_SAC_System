"""Annual grant, distribution among halls, hall expenditure, petty expenses and statement of accounts."""
import pytest

from tests.conftest import MONTH, ok


def grant(w, amount=100000, year=2026, who=None):
    return w.client.post("/api/grants", json={"year": year, "amount": amount}, headers=who or w.admin)


def allocate(w, hostel, amount, year=2026, who=None):
    return w.client.post("/api/grants/allocations", json={"year": year, "hostel_id": hostel["id"], "amount": amount},
                         headers=who or w.admin)


def spend(w, amount, hostel=None, who=None, year=2026):
    body = {"hostel_id": (hostel or w.jasper)["id"], "year": year, "category": "upkeep",
            "description": "Painting", "amount": amount}
    return w.client.post("/api/expenditures", json=body, headers=who or w.warden1)


def test_grant_rules(world):
    ok(grant(world), 201)
    assert grant(world).status_code == 409                          # one grant per year
    assert grant(world, year=1999).status_code == 422
    assert grant(world, amount=-1, year=2027).status_code == 422
    assert grant(world, year=2027, who=world.warden1).status_code == 403
    assert [g["year"] for g in ok(world.client.get("/api/grants", headers=world.warden1))] == [2026]


def test_allocation_cannot_exceed_grant(world):
    assert allocate(world, world.jasper, 10).status_code == 404     # no grant yet
    ok(grant(world), 201)
    ok(allocate(world, world.jasper, 60000))
    assert allocate(world, world.amber, 40001).status_code == 400   # 60000 + 40001 > 100000
    ok(allocate(world, world.amber, 40000))                         # exactly the remainder
    assert allocate(world, {"id": 9999}, 1).status_code == 404


def test_reallocation_replaces_previous_amount(world):
    ok(grant(world), 201)
    ok(allocate(world, world.jasper, 90000))
    ok(allocate(world, world.jasper, 30000))                        # lowering own allocation frees money
    ok(allocate(world, world.amber, 70000))
    rows = ok(world.client.get("/api/grants/allocations?year=2026", headers=world.admin))
    assert sorted(r["amount"] for r in rows) == [30000, 70000]
    assert len(ok(world.client.get("/api/grants/allocations?year=2026", headers=world.warden1))) == 1


def test_only_chairman_allocates(world):
    ok(grant(world), 201)
    for who in (world.warden1, world.clerk1, world.dean):
        assert allocate(world, world.jasper, 1, who=who).status_code == 403


def test_expenditure_limited_by_allocation(world):
    assert spend(world, 100).status_code == 400                     # nothing allocated
    ok(grant(world), 201)
    ok(allocate(world, world.jasper, 10000))
    ok(spend(world, 6000), 201)
    assert spend(world, 4001).status_code == 400                    # would overspend
    ok(spend(world, 4000), 201)                                     # exactly the remaining amount
    assert spend(world, 0.01).status_code == 400


def test_expenditure_authorization_and_validation(world):
    ok(grant(world), 201)
    ok(allocate(world, world.jasper, 10000))
    assert spend(world, 10, who=world.warden2).status_code == 403   # other hall
    assert spend(world, 10, who=world.clerk1).status_code == 403
    assert spend(world, 10, who=world.admin).status_code == 403
    assert spend(world, -10).status_code == 422
    assert spend(world, 10, year=2201).status_code == 422


def test_expenditure_listing(world):
    ok(grant(world), 201)
    ok(allocate(world, world.jasper, 10000))
    ok(allocate(world, world.amber, 10000))
    ok(spend(world, 100), 201)
    ok(spend(world, 200, hostel=world.amber, who=world.warden2), 201)
    assert len(ok(world.client.get("/api/expenditures?year=2026", headers=world.warden1))) == 1
    assert len(ok(world.client.get("/api/expenditures?year=2026", headers=world.admin))) == 2


def test_petty_expenses(world):
    c = world.client
    ok(c.post("/api/petty-expenses", json={"description": "Newspapers", "amount": 250}, headers=world.admin), 201)
    ok(c.post("/api/petty-expenses", json={"description": "Tap repair", "amount": 120, "spent_on": "2026-09-02"},
              headers=world.clerk1), 201)
    assert len(ok(c.get("/api/petty-expenses", headers=world.clerk1))) == 2
    assert c.post("/api/petty-expenses", json={"description": "x", "amount": 1}, headers=world.admin).status_code == 422
    assert c.post("/api/petty-expenses", json={"description": "Magazines", "amount": -1},
                  headers=world.admin).status_code == 422
    assert c.post("/api/petty-expenses", json={"description": "Magazines", "amount": 5},
                  headers=world.warden1).status_code == 403


def _full_year(world):
    """Seed one year of money movement for Jasper and return the expected hall figures."""
    c = world.client
    ok(grant(world), 201)
    ok(allocate(world, world.jasper, 60000))
    ok(spend(world, 5000), 201)
    ok(c.post("/api/mess-charges", json={"roll_no": "21JE0001", "month": MONTH, "amount": 3000}, headers=world.mess1), 201)
    ok(c.post("/api/payments", json={"roll_no": "21JE0001", "month": MONTH}, headers=world.student), 201)
    ok(c.post("/api/mess-sheet/cheques", json={"hostel_id": world.jasper["id"], "month": MONTH}, headers=world.admin), 201)
    ok(c.post("/api/staff", headers=world.clerk1, json={
        "hostel_id": world.jasper["id"], "name": "Ramesh", "address": "Dhanbad", "phone": "9000000000",
        "role": "gardener", "daily_pay": 400, "joined_on": "2026-01-01"}), 201)
    ok(c.post("/api/salaries/generate", json={"hostel_id": world.jasper["id"], "month": MONTH}, headers=world.clerk1))
    ok(c.post("/api/petty-expenses", json={"description": "Newspapers", "amount": 250, "spent_on": "2026-03-01"},
              headers=world.admin), 201)


def test_hall_statement_of_accounts(world):
    _full_year(world)
    st = ok(world.client.get("/api/statement?year=2026", headers=world.warden1))
    income = {i["head"]: i["amount"] for i in st["income"]}
    spent = {e["head"]: e["amount"] for e in st["expenditure"]}
    assert st["scope"] == "Jasper"
    assert income == {"Institute grant": 60000, "Room rent collected": 1500, "Amenity charges collected": 500,
                      "Mess charges collected": 3000}
    assert spent == {"Hall expenditure (upkeep, gardens, etc.)": 5000, "Staff salaries": 12000,
                     "Paid to mess managers": 3000}
    assert (st["total_income"], st["total_expenditure"], st["balance"]) == (65000, 20000, 45000)


def test_sac_statement_includes_petty_expenses(world):
    _full_year(world)
    st = ok(world.client.get("/api/statement?year=2026", headers=world.admin))
    assert st["scope"] == "SAC (all hostels)" and st["total_income"] == 105000
    assert {e["head"]: e["amount"] for e in st["expenditure"]}["SAC petty expenses"] == 250
    assert st["total_expenditure"] == 20250


def test_statement_for_a_year_without_activity_is_zero(world):
    st = ok(world.client.get("/api/statement?year=2030", headers=world.dean))
    assert (st["total_income"], st["total_expenditure"], st["balance"]) == (0, 0, 0)


def test_statement_access(world):
    c = world.client
    # a warden always gets their own hall, even when asking for another
    assert ok(c.get(f"/api/statement?year=2026&hostel_id={world.amber['id']}", headers=world.warden1))["scope"] == "Jasper"
    assert ok(c.get(f"/api/statement?year=2026&hostel_id={world.amber['id']}", headers=world.admin))["scope"] == "Amber"
    assert c.get("/api/statement?year=2026&hostel_id=9999", headers=world.admin).status_code == 404
    for who in (world.student, world.clerk1, world.mess1):
        assert c.get("/api/statement?year=2026", headers=who).status_code == 403
    assert c.get("/api/statement", headers=world.admin).status_code == 422          # year required
