"""End-to-end walk through the activity/state diagrams, plus the web pages."""
from tests.conftest import MONTH, PW, login, ok


def test_pages_and_health(client):
    assert "Sign in" in client.get("/").text
    assert client.get("/dashboard").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert ok(client.get("/api/health")) == {"status": "ok"}
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/does-not-exist").status_code == 404


def test_cors_allows_configured_origin_only(client):
    origin = "http://localhost:8000"
    pre = {"Access-Control-Request-Method": "GET"}
    allowed = client.options("/api/health", headers={"Origin": origin, **pre})
    assert allowed.headers.get("access-control-allow-origin") == origin
    blocked = client.options("/api/health", headers={"Origin": "http://evil.example", **pre})
    assert "access-control-allow-origin" not in blocked.headers


def test_student_lifecycle(world):
    """Admission -> RoomAllotted -> ActiveStudent -> MonthlyBilling -> DuePending -> PaymentReceived
    -> Complaint Registered -> ATR -> Resolved -> Statement -> Audit."""
    c = world.client
    letter = ok(c.get("/api/students/21JE0001/allotment-letter", headers=world.student))
    assert letter["room_no"] == "101"

    ok(c.post("/api/mess-charges", json={"roll_no": "21JE0001", "month": MONTH, "amount": 3100}, headers=world.mess1), 201)
    assert not ok(c.get(f"/api/dues?roll_no=21JE0001&month={MONTH}", headers=world.student))["paid"]   # DuePending
    ok(c.post("/api/payments", json={"roll_no": "21JE0001", "month": MONTH}, headers=world.student), 201)

    cid = ok(c.post("/api/complaints", json={"type": "repair", "repair_type": "fused light",
                                             "description": "Tube light fused"}, headers=world.student), 201)["id"]
    ok(c.post(f"/api/complaints/{cid}/atr", json={"atr": "Electrician replaced it"}, headers=world.warden1))

    ok(c.post("/api/grants", json={"year": 2026, "amount": 500000}, headers=world.admin), 201)
    st = ok(c.get("/api/statement?year=2026", headers=world.admin))
    assert st["total_income"] == 500000 + 3100 + 500 + 1500


def test_new_chairman_account_can_manage(world):
    ok(world.client.post("/api/users", headers=world.admin, json={
        "username": "chair2", "full_name": "Second Chair", "password": PW, "role": "chairman"}), 201)
    h = login(world.client, "chair2")
    ok(world.client.post("/api/hostels", json={"name": "Topaz", "amenity_charge": 100}, headers=h), 201)
