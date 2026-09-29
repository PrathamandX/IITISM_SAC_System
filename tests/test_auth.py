"""Authentication (JWT), user management and authorization edge cases."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.config import JWT_ALGORITHM, JWT_SECRET_KEY
from tests.conftest import PW, login, ok


def test_login_success_returns_token_and_role(client):
    body = ok(client.post("/api/auth/login", data={"username": "chairman", "password": "Admin@123"}))
    assert body["token_type"] == "bearer" and body["role"] == "chairman" and body["access_token"]


@pytest.mark.parametrize("username,password", [("chairman", "wrong"), ("nobody", "Admin@123"), ("", "")])
def test_login_rejects_bad_credentials(client, username, password):
    res = client.post("/api/auth/login", data={"username": username, "password": password})
    assert res.status_code in (401, 422)


def test_me_returns_current_user(client):
    me = ok(client.get("/api/auth/me", headers=login(client, "chairman", "Admin@123")))
    assert me["username"] == "chairman" and "password_hash" not in me


@pytest.mark.parametrize("headers", [
    {},                                              # no token
    {"Authorization": "Bearer not-a-jwt"},           # garbage
    {"Authorization": "Basic Y2hhaXJtYW46eA=="},     # wrong scheme
])
def test_protected_endpoint_requires_valid_token(client, headers):
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_expired_token_rejected(client):
    token = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                       JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_with_other_secret_rejected(client):
    token = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                       "attacker-secret-that-is-long-enough-000000", algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_for_nonexistent_user_rejected(client):
    token = jwt.encode({"sub": "999", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                       JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_change_password(world):
    c = world.client
    assert c.post("/api/auth/change-password", headers=world.clerk1,
                  json={"old_password": "wrong", "new_password": "NewPassw0rd"}).status_code == 400
    assert c.post("/api/auth/change-password", headers=world.clerk1,
                  json={"old_password": PW, "new_password": "short"}).status_code == 422
    assert c.post("/api/auth/change-password", headers=world.clerk1,
                  json={"old_password": PW, "new_password": "NewPassw0rd"}).status_code == 204
    assert c.post("/api/auth/login", data={"username": "clerk1", "password": PW}).status_code == 401
    login(c, "clerk1", "NewPassw0rd")


@pytest.mark.parametrize("body,code", [
    ({"role": "student"}, 400),                          # students only via admission
    ({"role": "warden", "hostel_id": None}, 400),        # hostel-scoped role needs a hostel
    ({"role": "clerk", "hostel_id": 9999}, 400),         # hostel must exist
    ({"username": "bad name!"}, 422),                    # invalid characters
    ({"username": "ab"}, 422),                           # too short
    ({"password": "short"}, 422),                        # weak password
    ({"role": "superuser"}, 422),                        # unknown role
    ({"username": "clerk1"}, 409),                       # duplicate username
])
def test_create_user_validation(world, body, code):
    base = {"username": "newuser", "full_name": "New User", "password": PW, "role": "clerk",
            "hostel_id": world.jasper["id"]}
    assert world.client.post("/api/users", json={**base, **body}, headers=world.admin).status_code == code


def test_only_chairman_manages_users(world):
    body = {"username": "x1234", "full_name": "X", "password": PW, "role": "dean"}
    for who in (world.warden1, world.clerk1, world.dean, world.student):
        assert world.client.post("/api/users", json=body, headers=who).status_code in (403, 422)
        assert world.client.get("/api/users", headers=who).status_code == 403


def test_user_list_excludes_students(world):
    users = ok(world.client.get("/api/users", headers=world.admin))
    assert all(u["role"] != "student" for u in users) and len(users) == 8


def test_deactivated_user_cannot_login_or_use_token(world):
    c = world.client
    uid = next(u["id"] for u in ok(c.get("/api/users", headers=world.admin)) if u["username"] == "clerk1")
    assert ok(c.patch(f"/api/users/{uid}/deactivate", headers=world.admin))["is_active"] is False
    assert c.get("/api/auth/me", headers=world.clerk1).status_code == 401
    assert c.post("/api/auth/login", data={"username": "clerk1", "password": PW}).status_code == 401


def test_chairman_cannot_deactivate_self_or_missing_user(world):
    me = ok(world.client.get("/api/auth/me", headers=world.admin))
    assert world.client.patch(f"/api/users/{me['id']}/deactivate", headers=world.admin).status_code == 400
    assert world.client.patch("/api/users/9999/deactivate", headers=world.admin).status_code == 404
