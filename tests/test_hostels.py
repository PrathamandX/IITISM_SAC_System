"""Hostels, rooms and occupancy."""
import pytest

from tests.conftest import make_student, ok


def test_create_and_list_hostels(world):
    names = [h["name"] for h in ok(world.client.get("/api/hostels", headers=world.student))]
    assert names == ["Amber", "Jasper"]  # sorted, visible to any logged-in user


@pytest.mark.parametrize("body,code", [
    ({"name": "Jasper", "amenity_charge": 100}, 409),   # duplicate name
    ({"name": "", "amenity_charge": 100}, 422),         # empty name
    ({"name": "Opal", "amenity_charge": -1}, 422),      # negative charge
    ({"name": "Opal"}, 422),                            # missing field
    ({"name": "Opal", "amenity_charge": "abc"}, 422),   # wrong type
])
def test_create_hostel_validation(world, body, code):
    assert world.client.post("/api/hostels", json=body, headers=world.admin).status_code == code


def test_only_chairman_creates_hostels_and_rooms(world):
    c, hid = world.client, world.jasper["id"]
    for who in (world.warden1, world.clerk1, world.dean, world.student):
        assert c.post("/api/hostels", json={"name": "Z", "amenity_charge": 1}, headers=who).status_code == 403
        assert c.post(f"/api/hostels/{hid}/rooms", json={"room_no": "9", "rent": 1}, headers=who).status_code == 403


def test_update_hostel(world):
    body = {"name": "Jasper", "amenity_charge": 650}
    assert ok(world.client.put(f"/api/hostels/{world.jasper['id']}", json=body, headers=world.admin))[
        "amenity_charge"] == 650
    assert world.client.put("/api/hostels/9999", json=body, headers=world.admin).status_code == 404


def test_room_rules(world):
    c, hid = world.client, world.jasper["id"]
    assert c.post(f"/api/hostels/{hid}/rooms", json={"room_no": "101", "rent": 1}, headers=world.admin).status_code == 409
    assert c.post("/api/hostels/9999/rooms", json={"room_no": "1", "rent": 1}, headers=world.admin).status_code == 404
    assert c.post(f"/api/hostels/{hid}/rooms", json={"room_no": "", "rent": 1}, headers=world.admin).status_code == 422
    # same room number is allowed in a different hostel
    assert c.post(f"/api/hostels/{world.amber['id']}/rooms", json={"room_no": "101", "rent": 900},
                  headers=world.admin).status_code == 201


def test_list_rooms_and_vacant_filter(world):
    c, hid = world.client, world.jasper["id"]
    rooms = ok(c.get(f"/api/hostels/{hid}/rooms", headers=world.clerk1))
    assert [(r["room_no"], r["is_occupied"]) for r in rooms] == [("101", True), ("102", False)]
    assert [r["room_no"] for r in ok(c.get(f"/api/hostels/{hid}/rooms?vacant_only=true", headers=world.clerk1))] == ["102"]
    assert c.get(f"/api/hostels/{hid}/rooms", headers=world.clerk2).status_code == 403   # other hostel
    assert c.get(f"/api/hostels/{hid}/rooms", headers=world.student).status_code == 403


def test_hostel_occupancy(world):
    c, hid = world.client, world.jasper["id"]
    assert ok(c.get(f"/api/hostels/{hid}/occupancy", headers=world.warden1)) == {
        "hostel_id": hid, "hostel": "Jasper", "total_rooms": 2, "occupied": 1, "vacant": 1}
    assert c.get(f"/api/hostels/{hid}/occupancy", headers=world.warden2).status_code == 403
    assert c.get("/api/hostels/9999/occupancy", headers=world.admin).status_code == 404


def test_overall_occupancy_updates_after_admission(world):
    c = world.client
    before = ok(c.get("/api/occupancy", headers=world.dean))
    assert (before["total_rooms"], before["occupied"], before["vacant"]) == (3, 1, 2)
    ok(make_student(c, world.clerk2, "21JE0002", world.amber["id"]), 201)
    after = ok(c.get("/api/occupancy", headers=world.dean))
    assert after["occupied"] == 2 and {h["hostel"]: h["occupied"] for h in after["hostels"]} == {"Amber": 1, "Jasper": 1}


def test_overall_occupancy_restricted(world):
    for who in (world.warden1, world.clerk1, world.student, world.mess1):
        assert world.client.get("/api/occupancy", headers=who).status_code == 403
