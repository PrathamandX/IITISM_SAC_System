"""Mess charges, dues (mess + amenity + rent), payments and the mess manager sheet/cheques."""
import pytest

from tests.conftest import MONTH, make_student, ok


def charge(w, amount=3000, month=MONTH, roll="21JE0001", who=None):
    return w.client.post("/api/mess-charges", json={"roll_no": roll, "month": month, "amount": amount},
                         headers=who or w.mess1)


def pay(w, month=MONTH, roll="21JE0001", who=None):
    return w.client.post("/api/payments", json={"roll_no": roll, "month": month}, headers=who or w.student)


def test_dues_formula(world):
    ok(charge(world), 201)
    dues = ok(world.client.get(f"/api/dues?roll_no=21JE0001&month={MONTH}", headers=world.student))
    assert dues == {"roll_no": "21JE0001", "month": MONTH, "mess_charge": 3000, "amenity_charge": 500,
                    "room_rent": 1500, "total_due": 5000, "paid": False}


def test_dues_without_mess_charge_is_rent_plus_amenity(world):
    dues = ok(world.client.get(f"/api/dues?roll_no=21JE0001&month={MONTH}", headers=world.clerk1))
    assert dues["mess_charge"] == 0 and dues["total_due"] == 2000


def test_payment_is_computed_server_side_and_only_once(world):
    ok(charge(world, 2750.50), 201)
    p = ok(pay(world), 201)
    assert p["total"] == 4750.50
    assert pay(world).status_code == 409                                                  # double payment
    assert ok(world.client.get(f"/api/dues?roll_no=21JE0001&month={MONTH}", headers=world.student))["paid"]


def test_payment_ignores_client_supplied_amount(world):
    ok(charge(world), 201)
    res = world.client.post("/api/payments", json={"roll_no": "21JE0001", "month": MONTH, "total": 1},
                            headers=world.student)
    assert ok(res, 201)["total"] == 5000


def test_cannot_pay_before_mess_charges_entered(world):
    assert pay(world).status_code == 400


def test_clerk_can_record_counter_payment(world):
    ok(charge(world), 201)
    ok(pay(world, who=world.clerk1), 201)


def test_mess_charge_can_be_corrected_until_paid(world):
    ok(charge(world, 3000), 201)
    assert ok(charge(world, 3200), 201)["amount"] == 3200
    ok(pay(world), 201)
    assert charge(world, 1).status_code == 409                                             # locked after payment


@pytest.mark.parametrize("month", ["2026-13", "2026-9", "26-09", "2026/09", "abcd-ef", ""])
def test_invalid_month_rejected(world, month):
    assert charge(world, month=month).status_code == 422
    assert world.client.get(f"/api/dues?roll_no=21JE0001&month={month}", headers=world.student).status_code == 422


@pytest.mark.parametrize("amount", [-1, "ten", None, 10_000_001])
def test_invalid_mess_amount_rejected(world, amount):
    assert charge(world, amount).status_code == 422


def test_zero_mess_charge_allowed_but_not_payable(world):
    ok(charge(world, 0), 201)                  # e.g. student on vacation all month
    assert pay(world).status_code == 400


def test_mess_charge_authorization(world):
    assert charge(world, who=world.mess2).status_code == 403    # other hostel's mess manager
    for who in (world.clerk1, world.warden1, world.student, world.admin):
        assert charge(world, who=who).status_code == 403


def test_unknown_student_or_no_room(world):
    assert charge(world, roll="NOPE").status_code == 404
    assert world.client.get(f"/api/dues?roll_no=NOPE&month={MONTH}", headers=world.clerk1).status_code == 404


def test_student_cannot_see_or_pay_others_dues(world):
    ok(make_student(world.client, world.clerk1, "21JE0002", world.jasper["id"]), 201)
    ok(charge(world, roll="21JE0002"), 201)
    assert world.client.get(f"/api/dues?roll_no=21JE0002&month={MONTH}", headers=world.student).status_code == 403
    assert pay(world, roll="21JE0002").status_code == 403


def test_payments_list_scoping(world):
    c = world.client
    ok(make_student(c, world.clerk2, "21JE0002", world.amber["id"]), 201)
    ok(charge(world), 201)
    ok(charge(world, roll="21JE0002", who=world.mess2), 201)
    ok(pay(world), 201)
    ok(pay(world, roll="21JE0002", who=world.clerk2), 201)
    assert len(ok(c.get("/api/payments", headers=world.student))) == 1
    assert len(ok(c.get("/api/payments", headers=world.clerk1))) == 1
    assert len(ok(c.get("/api/payments", headers=world.admin))) == 2
    assert len(ok(c.get("/api/payments?month=2026-10", headers=world.admin))) == 0


def test_mess_charge_list_scoping(world):
    ok(charge(world), 201)
    assert len(ok(world.client.get(f"/api/mess-charges?month={MONTH}", headers=world.mess1))) == 1
    assert len(ok(world.client.get(f"/api/mess-charges?month={MONTH}", headers=world.mess2))) == 0
    assert world.client.get(f"/api/mess-charges?month={MONTH}", headers=world.student).status_code == 403


def test_mess_sheet_only_counts_collected_money(world):
    c = world.client
    ok(make_student(c, world.clerk1, "21JE0002", world.jasper["id"]), 201)
    ok(charge(world, 3000), 201)
    ok(charge(world, 2000, roll="21JE0002"), 201)
    ok(pay(world), 201)                                         # only the first student paid
    sheet = {r["hostel"]: r for r in ok(c.get(f"/api/mess-sheet?month={MONTH}", headers=world.clerk1))}
    assert sheet["Jasper"]["amount_due"] == 3000 and sheet["Jasper"]["mess_manager"] == "Mess1"
    assert sheet["Amber"]["amount_due"] == 0 and sheet["Jasper"]["cheque_no"] is None


def test_mess_cheque_lifecycle(world):
    c, body = world.client, {"hostel_id": world.jasper["id"], "month": MONTH}
    assert c.post("/api/mess-sheet/cheques", json=body, headers=world.admin).status_code == 400  # nothing collected
    ok(charge(world), 201)
    ok(pay(world), 201)
    assert c.post("/api/mess-sheet/cheques", json=body, headers=world.clerk1).status_code == 403  # chairman only
    cheque = ok(c.post("/api/mess-sheet/cheques", json=body, headers=world.admin), 201)
    assert cheque["amount"] == 3000 and cheque["cheque_no"] == f"MESS-{MONTH}-{world.jasper['id']}" and not cheque["signed"]
    assert c.post("/api/mess-sheet/cheques", json=body, headers=world.admin).status_code == 409   # no duplicate cheque
    assert ok(c.post(f"/api/mess-sheet/cheques/{cheque['id']}/sign", headers=world.admin))["signed"]
    assert c.post("/api/mess-sheet/cheques/9999/sign", headers=world.admin).status_code == 404
    row = next(r for r in ok(c.get(f"/api/mess-sheet?month={MONTH}", headers=world.admin)) if r["hostel"] == "Jasper")
    assert row["signed"] and row["cheque_no"] == cheque["cheque_no"]
    assert len(ok(c.get(f"/api/mess-sheet/cheques?month={MONTH}", headers=world.clerk1))) == 1


def test_mess_cheque_requires_mess_manager_account(world):
    c = world.client
    opal = ok(c.post("/api/hostels", json={"name": "Opal", "amenity_charge": 0}, headers=world.admin), 201)
    res = c.post("/api/mess-sheet/cheques", json={"hostel_id": opal["id"], "month": MONTH}, headers=world.admin)
    assert res.status_code == 400


def test_mess_sheet_access(world):
    for who in (world.student, world.warden1, world.mess1, world.dean):
        assert world.client.get(f"/api/mess-sheet?month={MONTH}", headers=who).status_code == 403
