import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
client.__enter__()

# The lifespan seeds the demo admin from settings.ADMIN_USERNAME /
# settings.ADMIN_PASSWORD (see app/main.py), which come from .env and
# can legitimately differ between local dev and CI. Read them from the
# same source the app uses instead of hardcoding "admin"/"facilityops123",
# so these tests can't drift out of sync with whatever actually got seeded.
ADMIN_USERNAME = settings.ADMIN_USERNAME
ADMIN_PASSWORD = settings.ADMIN_PASSWORD


def test_login_with_seeded_admin_succeeds():
    r = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["username"] == ADMIN_USERNAME
    assert len(body["access_token"]) > 20


def test_login_wrong_password_rejected():
    r = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": "definitely-wrong"})
    assert r.status_code == 401


def test_login_unknown_user_rejected_same_as_wrong_password():
    """Same status/detail for 'no such user' as for 'wrong password' —
    distinguishing them would let someone enumerate valid usernames."""
    r1 = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    r2 = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": "whatever"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_me_requires_valid_token():
    r = client.get("/api/auth/me")
    assert r.status_code == 401

    login = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    token = login.json()["access_token"]
    r2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == ADMIN_USERNAME


def test_me_rejects_garbage_token():
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_public_register_creates_technician_and_auto_logs_in():
    import uuid
    username = f"new_user_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={"username": username, "password": "pw123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == username
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20

    # The returned token should work immediately (auto-login) and the
    # account should be "technician", never "admin" via self-signup.
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "technician"


def test_register_rejects_duplicate_username():
    import uuid
    username = f"dup_signup_{uuid.uuid4().hex[:8]}"
    r1 = client.post("/api/auth/register", json={"username": username, "password": "pw123456"})
    assert r1.status_code == 200
    r2 = client.post("/api/auth/register", json={"username": username, "password": "different_pw"})
    assert r2.status_code == 409


def test_register_rejects_short_username_and_password():
    r1 = client.post("/api/auth/register", json={"username": "ab", "password": "pw123456"})
    assert r1.status_code == 400
    r2 = client.post("/api/auth/register", json={"username": "valid_username", "password": "short"})
    assert r2.status_code == 400


def _admin_headers():
    login = client.post("/api/auth/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_admin_can_create_and_list_and_delete_technician():
    headers = _admin_headers()

    r = client.post("/api/auth/users", json={"username": "tech_rbac_test", "password": "pw12345", "role": "technician"}, headers=headers)
    assert r.status_code == 200
    user_id = r.json()["id"]
    assert r.json()["role"] == "technician"

    r2 = client.get("/api/auth/users", headers=headers)
    assert r2.status_code == 200
    assert any(u["username"] == "tech_rbac_test" for u in r2.json())

    r3 = client.delete(f"/api/auth/users/{user_id}", headers=headers)
    assert r3.status_code == 200


def test_create_user_rejects_invalid_role():
    headers = _admin_headers()
    r = client.post("/api/auth/users", json={"username": "bad_role_user", "password": "pw12345", "role": "superuser"}, headers=headers)
    assert r.status_code == 400


def test_create_user_rejects_duplicate_username():
    headers = _admin_headers()
    r = client.post("/api/auth/users", json={"username": ADMIN_USERNAME, "password": "whatever", "role": "technician"}, headers=headers)
    assert r.status_code == 409


def test_admin_cannot_delete_own_account():
    headers = _admin_headers()
    me = client.get("/api/auth/me", headers=headers).json()
    r = client.get("/api/auth/users", headers=headers)
    my_id = next(u["id"] for u in r.json() if u["username"] == me["username"])
    r2 = client.delete(f"/api/auth/users/{my_id}", headers=headers)
    assert r2.status_code == 400


def test_technician_can_manage_records_but_not_users():
    admin_headers = _admin_headers()
    created = client.post("/api/auth/users", json={"username": "tech_records_test", "password": "pw12345", "role": "technician"}, headers=admin_headers)
    tech_id = created.json()["id"]

    tech_login = client.post("/api/auth/login", json={"username": "tech_records_test", "password": "pw12345"})
    tech_headers = {"Authorization": f"Bearer {tech_login.json()['access_token']}"}

    # Technician CAN manage domain records (same as admin)...
    r = client.post("/api/cost/records", json={
        "vendor_name": "Tech Test Vendor", "category": "Repairs & Maintenance", "amount_inr": 1.0,
    }, headers=tech_headers)
    assert r.status_code == 200
    client.delete(f"/api/cost/records/{r.json()['id']}", headers=tech_headers)

    # ...but CANNOT manage other users (admin-only action).
    r2 = client.post("/api/auth/users", json={"username": "should_fail", "password": "pw12345", "role": "technician"}, headers=tech_headers)
    assert r2.status_code == 403

    client.delete(f"/api/auth/users/{tech_id}", headers=admin_headers)