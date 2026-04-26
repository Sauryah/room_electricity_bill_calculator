"""Backend API tests for the Room Bill Splitter.

Covers:
- /api/health
- /api/login (success, wrong password, non-existent, validation)
- /api/calculate (auth required, invalid token, valid calc, business rules,
  pydantic validation)
- JWT structure (HS256, contains user_id + username)
- Admin user seeded in PostgreSQL
"""
import os
import base64
import json
import pytest
import requests

# Use localhost as instructed by main agent for backend-only test
BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# -----------------------
# Fixtures
# -----------------------
@pytest.fixture(scope="session")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session) -> str:
    resp = session.post(
        f"{API}/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    return data["access_token"]


@pytest.fixture()
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# -----------------------
# Health
# -----------------------
class TestHealth:
    def test_health_ok(self, session):
        resp = session.get(f"{API}/health", timeout=10)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# -----------------------
# Login
# -----------------------
class TestLogin:
    def test_login_success_returns_jwt(self, session):
        resp = session.post(
            f"{API}/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data.get("access_token"), str)
        assert len(data["access_token"]) > 20
        assert data.get("token_type") == "bearer"
        assert isinstance(data.get("user_id"), str) and len(data["user_id"]) > 0
        assert data.get("username") == ADMIN_USERNAME

    def test_login_jwt_uses_hs256_and_contains_claims(self, session):
        resp = session.post(
            f"{API}/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # JWT has 3 parts
        parts = token.split(".")
        assert len(parts) == 3, "Token is not a JWT (must have 3 parts)"

        def b64url_decode(seg: str) -> bytes:
            seg = seg + "=" * (-len(seg) % 4)
            return base64.urlsafe_b64decode(seg.encode("utf-8"))

        header = json.loads(b64url_decode(parts[0]))
        body = json.loads(b64url_decode(parts[1]))

        assert header.get("alg") == "HS256"
        assert header.get("typ") == "JWT"
        assert body.get("user_id"), "user_id missing in JWT"
        assert body.get("username") == ADMIN_USERNAME
        assert "exp" in body and "iat" in body

    def test_login_username_is_case_insensitive(self, session):
        # The API lowercases the username, so 'ADMIN' should work
        resp = session.post(
            f"{API}/login",
            json={"username": "ADMIN", "password": ADMIN_PASSWORD},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_login_wrong_password_returns_401(self, session):
        resp = session.post(
            f"{API}/login",
            json={"username": ADMIN_USERNAME, "password": "wrongpass"},
            timeout=10,
        )
        assert resp.status_code == 401
        assert resp.json().get("detail") == "Invalid username or password"

    def test_login_unknown_user_returns_401(self, session):
        resp = session.post(
            f"{API}/login",
            json={"username": "ghost_user_xyz_TEST", "password": "whatever"},
            timeout=10,
        )
        assert resp.status_code == 401
        assert resp.json().get("detail") == "Invalid username or password"

    def test_login_missing_password_returns_422(self, session):
        resp = session.post(
            f"{API}/login",
            json={"username": ADMIN_USERNAME},
            timeout=10,
        )
        assert resp.status_code == 422

    def test_login_missing_username_returns_422(self, session):
        resp = session.post(
            f"{API}/login",
            json={"password": ADMIN_PASSWORD},
            timeout=10,
        )
        assert resp.status_code == 422

    def test_login_empty_strings_returns_422(self, session):
        resp = session.post(
            f"{API}/login",
            json={"username": "", "password": ""},
            timeout=10,
        )
        assert resp.status_code == 422


# -----------------------
# Calculate (auth)
# -----------------------
class TestCalculateAuth:
    def test_calculate_without_auth_returns_401(self, session):
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1500,
                "total_days": 30,
                "roommates": [{"name": "Alice", "days": 20}],
            },
            timeout=10,
        )
        assert resp.status_code == 401
        assert resp.json().get("detail") == "Missing authentication token"

    def test_calculate_invalid_bearer_token_returns_401(self, session):
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1500,
                "total_days": 30,
                "roommates": [{"name": "Alice", "days": 20}],
            },
            headers={
                "Authorization": "Bearer not-a-real-jwt-token",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        assert resp.status_code == 401
        # Any of "Invalid or expired token" / "Invalid token payload" is fine
        assert resp.json().get("detail") in (
            "Invalid or expired token",
            "Invalid token payload",
        )


# -----------------------
# Calculate (business logic)
# -----------------------
class TestCalculateLogic:
    def test_calculate_alice_bob_classic(self, session, auth_headers):
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1500,
                "total_days": 30,
                "roommates": [
                    {"name": "Alice", "days": 20},
                    {"name": "Bob", "days": 10},
                ],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_bill"] == 1500
        assert data["total_days"] == 30
        assert data["total_days_present"] == 30
        rooms = {r["name"]: r for r in data["roommates"]}

        assert rooms["Alice"]["amount"] == 1000.0
        assert rooms["Bob"]["amount"] == 500.0
        # Percentages 66.67 / 33.33 (4 decimals -> 66.6667 / 33.3333)
        assert abs(rooms["Alice"]["percentage"] - 66.6667) < 0.01
        assert abs(rooms["Bob"]["percentage"] - 33.3333) < 0.01
        # Sum of amounts = total bill
        assert abs(sum(r["amount"] for r in data["roommates"]) - 1500.0) < 0.01

    def test_calculate_rejects_roommate_days_exceeding_total(self, session, auth_headers):
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1000,
                "total_days": 10,
                "roommates": [{"name": "Alice", "days": 11}],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 400
        assert "cannot exceed" in resp.json().get("detail", "")

    def test_calculate_rejects_zero_total_days_present(self, session, auth_headers):
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1000,
                "total_days": 30,
                "roommates": [
                    {"name": "Alice", "days": 0},
                    {"name": "Bob", "days": 0},
                ],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 400
        assert "zero" in resp.json().get("detail", "").lower()

    def test_calculate_total_bill_must_be_positive(self, session, auth_headers):
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 0,
                "total_days": 30,
                "roommates": [{"name": "Alice", "days": 10}],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422

        resp2 = session.post(
            f"{API}/calculate",
            json={
                "total_bill": -100,
                "total_days": 30,
                "roommates": [{"name": "Alice", "days": 10}],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp2.status_code == 422

    def test_calculate_total_days_must_be_1_to_31(self, session, auth_headers):
        # 0 days
        resp = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1000,
                "total_days": 0,
                "roommates": [{"name": "Alice", "days": 0}],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422

        # 32 days
        resp2 = session.post(
            f"{API}/calculate",
            json={
                "total_bill": 1000,
                "total_days": 32,
                "roommates": [{"name": "Alice", "days": 10}],
            },
            headers=auth_headers,
            timeout=10,
        )
        assert resp2.status_code == 422

    def test_calculate_empty_roommates_returns_422(self, session, auth_headers):
        resp = session.post(
            f"{API}/calculate",
            json={"total_bill": 1000, "total_days": 30, "roommates": []},
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 422


# -----------------------
# DB / Seed
# -----------------------
class TestSeed:
    def test_admin_seeded_via_login(self, session):
        """Confirms admin user exists in the DB by logging in successfully."""
        resp = session.post(
            f"{API}/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == ADMIN_USERNAME

    def test_admin_password_is_bcrypt_in_db(self):
        """Verify the seeded password is bcrypt-hashed ($2b$...)."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except Exception:
            pytest.skip("psycopg2 not available in this env")

        dsn = os.environ.get(
            "DATABASE_URL",
            "postgresql://billsplitter:billsplitter@localhost:5432/billsplitter",
        )
        try:
            conn = psycopg2.connect(dsn)
        except Exception as e:
            pytest.skip(f"Cannot connect to Postgres: {e}")

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT username, password_hash FROM users WHERE username = %s",
                    (ADMIN_USERNAME,),
                )
                row = cur.fetchone()
            assert row is not None, "admin user not present in DB"
            assert row["password_hash"].startswith("$2b$") or row["password_hash"].startswith(
                "$2a$"
            ), f"password_hash is not bcrypt: {row['password_hash'][:10]}..."
        finally:
            conn.close()
