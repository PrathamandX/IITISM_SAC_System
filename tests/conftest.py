"""Shared test fixtures.

Every test gets a fresh, empty database (SQLite file, so PostgreSQL is not needed to run the suite)
and, through the `world` fixture, a small seeded campus:

    Jasper hostel (amenity 500): rooms 101, 102 (rent 1500)   staff: clerk1, warden1, mess1
    Amber  hostel (amenity 300): room  A1       (rent 1000)   staff: clerk2, warden2, mess2
    dean (controlling warden), chairman (admin), student 21JE0001 in Jasper room 101
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

DB_FILE = Path(__file__).parent / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-only-0000000000"
os.environ["ADMIN_USERNAME"] = "chairman"
os.environ["ADMIN_PASSWORD"] = "Admin@123"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bcrypt  # noqa: E402

# Cheap hashing keeps the suite fast; production code uses bcrypt's default cost.
_gensalt = bcrypt.gensalt
bcrypt.gensalt = lambda rounds=4, prefix=b"2b": _gensalt(4, prefix)

from fastapi.testclient import TestClient  # noqa: E402

from backend.database import Base, engine  # noqa: E402
from main import app, create_first_admin  # noqa: E402

PW = "Passw0rd!"
MONTH = "2026-09"


@pytest.fixture(scope="session")
def app_client():
    with TestClient(app) as c:
        yield c
    engine.dispose()
    DB_FILE.unlink(missing_ok=True)


@pytest.fixture
def client(app_client):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    create_first_admin()
    return app_client


def login(client, username, password=PW):
    res = client.post("/api/auth/login", data={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def ok(res, code=200):
    assert res.status_code == code, f"expected {code}, got {res.status_code}: {res.text}"
    return res.json() if res.content else None


def make_student(client, headers, roll, hostel_id, **extra):
    body = {"roll_no": roll, "name": "Student " + roll, "address": "Dhanbad, Jharkhand", "phone": "9876543210",
            "admission_note_ref": "ADM/" + roll, "hostel_id": hostel_id, "password": PW, **extra}
    return client.post("/api/students", json=body, headers=headers)


@pytest.fixture
def world(client):
    admin = login(client, "chairman", "Admin@123")
    jasper = ok(client.post("/api/hostels", json={"name": "Jasper", "amenity_charge": 500}, headers=admin), 201)
    amber = ok(client.post("/api/hostels", json={"name": "Amber", "amenity_charge": 300}, headers=admin), 201)
    rooms = [ok(client.post(f"/api/hostels/{jasper['id']}/rooms", json={"room_no": no, "rent": 1500},
                            headers=admin), 201) for no in ("101", "102")]
    rooms.append(ok(client.post(f"/api/hostels/{amber['id']}/rooms", json={"room_no": "A1", "rent": 1000},
                                headers=admin), 201))
    accounts = [("clerk1", "clerk", jasper), ("warden1", "warden", jasper), ("mess1", "mess_manager", jasper),
                ("clerk2", "clerk", amber), ("warden2", "warden", amber), ("mess2", "mess_manager", amber),
                ("dean", "controlling_warden", None)]
    for username, role, hostel in accounts:
        ok(client.post("/api/users", headers=admin, json={
            "username": username, "full_name": username.title(), "password": PW, "role": role,
            "hostel_id": hostel["id"] if hostel else None}), 201)
    h = {u: login(client, u) for u, _, _ in accounts}
    ok(make_student(client, h["clerk1"], "21JE0001", jasper["id"]), 201)
    return SimpleNamespace(client=client, admin=admin, jasper=jasper, amber=amber, rooms=rooms,
                           student=login(client, "21JE0001"), **h)
