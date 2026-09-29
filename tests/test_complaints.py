"""Complaints (repair / behavior) and Action Taken Reports."""
import pytest

from tests.conftest import make_student, ok

REPAIR = {"type": "repair", "repair_type": "water tap", "description": "Tap in bathroom is leaking"}
BEHAVIOR = {"type": "behavior", "against": "mess staff", "description": "Rude behaviour at dinner"}


def raise_(w, body=REPAIR, who=None):
    return w.client.post("/api/complaints", json=body, headers=who or w.student)


def test_raise_repair_and_behavior_complaints(world):
    r = ok(raise_(world), 201)
    assert (r["status"], r["atr"], r["hostel_id"]) == ("open", None, world.jasper["id"])
    assert ok(raise_(world, BEHAVIOR), 201)["against"] == "mess staff"


@pytest.mark.parametrize("body", [
    {"type": "repair", "description": "Something broke"},                     # repair_type missing
    {"type": "behavior", "description": "Someone was rude"},                  # against missing
    {**REPAIR, "description": "bad"},                                         # description too short
    {**REPAIR, "type": "other"},                                              # unknown type
    {**REPAIR, "description": "x" * 2001},                                    # too long
])
def test_complaint_validation(world, body):
    assert raise_(world, body).status_code == 422


def test_only_students_raise_complaints(world):
    for who in (world.warden1, world.clerk1, world.admin):
        assert raise_(world, who=who).status_code == 403


def test_complaint_visibility(world):
    c = world.client
    ok(make_student(c, world.clerk2, "21JE0002", world.amber["id"]), 201)
    other = __import__("tests.conftest", fromlist=["login"]).login(c, "21JE0002")
    ok(raise_(world), 201)
    ok(raise_(world, who=other), 201)
    count = lambda h: len(ok(c.get("/api/complaints", headers=h)))  # noqa: E731
    assert (count(world.student), count(world.warden1), count(world.clerk2), count(world.dean), count(world.admin)) == (
        1, 1, 1, 2, 2)
    assert c.get("/api/complaints", headers=world.mess1).status_code == 403


def test_warden_posts_atr_and_resolves(world):
    c = world.client
    cid = ok(raise_(world), 201)["id"]
    done = ok(c.post(f"/api/complaints/{cid}/atr", json={"atr": "Plumber replaced the tap"}, headers=world.warden1))
    assert done["status"] == "resolved" and done["resolved_at"] and done["atr"] == "Plumber replaced the tap"
    assert ok(c.get("/api/complaints", headers=world.student))[0]["atr"] == "Plumber replaced the tap"


def test_atr_without_resolving_keeps_complaint_open(world):
    cid = ok(raise_(world), 201)["id"]
    res = ok(world.client.post(f"/api/complaints/{cid}/atr", json={"atr": "Plumber called", "resolve": False},
                               headers=world.warden1))
    assert res["status"] == "open" and res["resolved_at"] is None


def test_atr_rules(world):
    c = world.client
    cid = ok(raise_(world), 201)["id"]
    assert c.post(f"/api/complaints/{cid}/atr", json={"atr": "Fixed it"}, headers=world.warden2).status_code == 403
    assert c.post(f"/api/complaints/{cid}/atr", json={"atr": "Fixed it"}, headers=world.clerk1).status_code == 403
    assert c.post(f"/api/complaints/{cid}/atr", json={"atr": "Fixed it"}, headers=world.student).status_code == 403
    assert c.post(f"/api/complaints/{cid}/atr", json={"atr": "ok"}, headers=world.warden1).status_code == 422
    assert c.post("/api/complaints/9999/atr", json={"atr": "Fixed it"}, headers=world.warden1).status_code == 404


def test_status_filter(world):
    c = world.client
    cid = ok(raise_(world), 201)["id"]
    ok(raise_(world, BEHAVIOR), 201)
    ok(c.post(f"/api/complaints/{cid}/atr", json={"atr": "Fixed the tap"}, headers=world.warden1))
    assert len(ok(c.get("/api/complaints?status=open", headers=world.warden1))) == 1
    assert len(ok(c.get("/api/complaints?status=resolved", headers=world.warden1))) == 1
    assert c.get("/api/complaints?status=closed", headers=world.warden1).status_code == 422
