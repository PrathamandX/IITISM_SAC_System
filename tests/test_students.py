"""Admission, room allotment, allotment letter and photographs."""
import pytest

from tests.conftest import make_student, ok

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def test_admission_auto_allots_first_vacant_room(world):
    s = ok(make_student(world.client, world.clerk1, "21JE0002", world.jasper["id"]), 201)
    assert s["room_id"] == world.rooms[1]["id"]          # 101 is taken, so 102


def test_admission_to_a_chosen_room(world):
    s = ok(make_student(world.client, world.admin, "21JE0002", world.amber["id"], room_id=world.rooms[2]["id"]), 201)
    assert s["room_id"] == world.rooms[2]["id"]


def test_admission_room_rules(world):
    c, jid = world.client, world.jasper["id"]
    assert make_student(c, world.clerk1, "ROLLX1", jid, room_id=world.rooms[2]["id"]).status_code == 400  # other hostel
    assert make_student(c, world.clerk1, "ROLLX2", jid, room_id=world.rooms[0]["id"]).status_code == 409  # occupied
    assert make_student(c, world.clerk1, "ROLLX3", jid, room_id=99999).status_code == 400                  # no such room
    ok(make_student(c, world.clerk1, "ROLLX4", jid), 201)                                                   # last room
    assert make_student(c, world.clerk1, "ROLLX5", jid).status_code == 409                                  # hostel full
    assert make_student(c, world.admin, "ROLLX6", 9999).status_code == 404                                  # no hostel


def test_admission_duplicate_roll_number(world):
    assert make_student(world.client, world.clerk1, "21JE0001", world.jasper["id"]).status_code == 409


@pytest.mark.parametrize("field,value", [
    ("phone", "abc"), ("phone", "12"), ("roll_no", "21 JE"), ("roll_no", "ab"), ("name", ""),
    ("address", "x"), ("password", "short"), ("admission_note_ref", ""),
])
def test_admission_field_validation(world, field, value):
    res = make_student(world.client, world.clerk1, "21JE0009", world.jasper["id"], **{field: value})
    assert res.status_code == 422


def test_admission_authorization(world):
    c = world.client
    assert make_student(c, world.clerk2, "ROLLY1", world.jasper["id"]).status_code == 403   # other hostel's clerk
    for who in (world.warden1, world.mess1, world.dean, world.student):
        assert make_student(c, who, "ROLLY2", world.jasper["id"]).status_code == 403


def test_admitted_student_can_login_and_see_profile(world):
    me = ok(world.client.get("/api/students/me", headers=world.student))
    assert me["roll_no"] == "21JE0001" and me["room_id"] == world.rooms[0]["id"]
    assert world.client.get("/api/students/me", headers=world.clerk1).status_code == 403


def test_allotment_letter(world):
    letter = ok(world.client.get("/api/students/21JE0001/allotment-letter", headers=world.student))
    assert (letter["hostel"], letter["room_no"], letter["monthly_rent"], letter["monthly_amenity_charge"]) == (
        "Jasper", "101", 1500, 500)
    assert letter["letter_no"].startswith("SAC/ALLOT/")


def test_allotment_letter_access(world):
    c = world.client
    ok(make_student(c, world.clerk1, "21JE0002", world.jasper["id"]), 201)
    assert c.get("/api/students/21JE0002/allotment-letter", headers=world.student).status_code == 403
    assert c.get("/api/students/21JE0001/allotment-letter", headers=world.clerk2).status_code == 403
    assert c.get("/api/students/NOPE/allotment-letter", headers=world.admin).status_code == 404


def test_student_list_is_scoped(world):
    c = world.client
    ok(make_student(c, world.clerk2, "21JE0002", world.amber["id"]), 201)
    assert [s["roll_no"] for s in ok(c.get("/api/students", headers=world.clerk1))] == ["21JE0001"]
    assert [s["roll_no"] for s in ok(c.get("/api/students", headers=world.clerk2))] == ["21JE0002"]
    # a clerk cannot widen the scope with a query parameter
    assert [s["roll_no"] for s in ok(c.get(f"/api/students?hostel_id={world.amber['id']}", headers=world.clerk1))] == [
        "21JE0001"]
    assert len(ok(c.get("/api/students", headers=world.admin))) == 2
    assert c.get("/api/students", headers=world.student).status_code == 403


def test_photo_upload(world):
    c = world.client
    res = ok(c.post("/api/students/21JE0001/photo", headers=world.student,
                    files={"photo": ("me.png", PNG, "image/png")}))
    assert res["photo_path"].startswith("/static/uploads/") and res["photo_path"].endswith(".png")
    assert c.get(res["photo_path"]).status_code == 200


@pytest.mark.parametrize("name,content,ctype", [
    ("evil.exe", b"MZ", "application/octet-stream"),   # not an image
    ("a.gif", b"GIF89a", "image/gif"),                # image type not allowed
    ("big.png", b"0" * (2 * 1024 * 1024 + 1), "image/png"),  # over 2 MB
], ids=["exe", "gif", "too-large"])
def test_photo_upload_rejections(world, name, content, ctype):
    res = world.client.post("/api/students/21JE0001/photo", headers=world.clerk1, files={"photo": (name, content, ctype)})
    assert res.status_code == 400


def test_photo_upload_access(world):
    c = world.client
    ok(make_student(c, world.clerk1, "21JE0002", world.jasper["id"]), 201)
    files = {"photo": ("me.png", PNG, "image/png")}
    assert c.post("/api/students/21JE0002/photo", headers=world.student, files=files).status_code == 403
    assert c.post("/api/students/21JE0001/photo", headers=world.warden1, files=files).status_code == 403
