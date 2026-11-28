import os
os.environ["TESTING"] = "1"

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
app.state.testing = True
from backend.app.database import Base, get_db
from backend.app.models import Destination, User, UserSession, CrowdReport, TravelPost, PostComment
from backend.app.services.auth import hash_password

TEST_DB_URL = "sqlite:///:memory:"
engine_test = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    db.add(Destination(id="amber", name="Amber Fort", base_crowd=62, is_gem=False, alternatives=[]))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine_test)


def _create_admin(email: str = "admin@raahi.gov.in", password: str = "AdminPass123") -> User:
    db = TestingSessionLocal()
    user = User(
        id=f"adm_{uuid.uuid4().hex[:10]}",
        username="DoT Admin",
        email=email.lower(),
        password_hash=hash_password(password),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_tourist_signup_succeeds_and_stores_argon2id_hash():
    client = TestClient(app)
    res = client.post(
        "/api/auth/signup",
        json={"name": "Aarav Sharma", "email": "Aarav@Example.com", "password": "Password123"},
    )
    assert res.status_code == 201
    user_data = res.json()["user"]
    assert user_data["name"] == "Aarav Sharma"
    assert user_data["email"] == "aarav@example.com"
    assert user_data["role"] == "tourist"
    assert "raahi_session" in client.cookies

    db = TestingSessionLocal()
    db_user = db.query(User).filter(User.email == "aarav@example.com").first()
    assert db_user is not None
    assert db_user.password_hash is not None
    assert db_user.password_hash != "Password123"
    assert db_user.password_hash.startswith("$argon2id$")
    db.close()


def test_duplicate_email_signup_rejected():
    client = TestClient(app)
    r1 = client.post(
        "/api/auth/signup",
        json={"name": "Priya", "email": "priya@example.com", "password": "Password123"},
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/auth/signup",
        json={"name": "Priya 2", "email": "  PRIYA@example.com ", "password": "Password123"},
    )
    assert r2.status_code == 409


def test_public_signup_cannot_create_admin_account():
    client = TestClient(app)
    res = client.post(
        "/api/auth/signup",
        json={
            "name": "Attacker",
            "email": "attacker@example.com",
            "password": "Password123",
            "role": "admin",
        },
    )
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "tourist"

    db = TestingSessionLocal()
    db_user = db.query(User).filter(User.email == "attacker@example.com").first()
    assert db_user is not None
    assert db_user.role == "tourist"
    db.close()


def test_login_success_session_persistence_and_logout_invalidation():
    client = TestClient(app)
    client.post(
        "/api/auth/signup",
        json={"name": "Meera", "email": "meera@example.com", "password": "Password123"},
    )
    client.post("/api/auth/logout")

    # Wrong password fails
    bad = client.post(
        "/api/auth/login",
        json={"email": "meera@example.com", "password": "WrongPassword1"},
    )
    assert bad.status_code == 401

    # Correct login succeeds
    good = client.post(
        "/api/auth/login",
        json={"email": "meera@example.com", "password": "Password123"},
    )
    assert good.status_code == 200
    assert good.json()["user"]["email"] == "meera@example.com"

    # Session persists across /api/auth/me (simulating refresh)
    me1 = client.get("/api/auth/me")
    assert me1.status_code == 200
    assert me1.json()["user"]["name"] == "Meera"

    # Capture raw cookie and verify logout revokes server session
    session_cookie = client.cookies.get("raahi_session")
    assert session_cookie

    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    # Replaying old cookie after logout fails because session is revoked in DB
    replay_client = TestClient(app)
    replay_client.cookies.set("raahi_session", session_cookie)
    assert replay_client.get("/api/auth/me").status_code == 401


def test_tourist_cannot_access_admin_and_admin_can_moderate():
    # Tourist signs up
    tourist = TestClient(app)
    t_res = tourist.post(
        "/api/auth/signup",
        json={"name": "Rohan", "email": "rohan@example.com", "password": "Password123"},
    )
    tourist_id = t_res.json()["user"]["id"]

    # Tourist submits report; forged X-User-Id header is ignored
    rep_res = tourist.post(
        "/api/crowd-reports",
        json={"destination_id": "amber", "crowd_level": "Moderate", "tip": "Smooth entry"},
        headers={"X-User-Id": "forged_other_user"},
    )
    assert rep_res.status_code == 201
    report = rep_res.json()["report"]
    assert report["user_id"] == tourist_id
    assert report["moderation_status"] == "pending"

    # Tourist receives 403 Forbidden on admin endpoints
    assert tourist.get("/api/admin/reports").status_code == 403
    assert tourist.patch(f"/api/admin/reports/{report['id']}", json={"status": "approved"}).status_code == 403
    assert tourist.get("/api/admin/comments").status_code == 403

    # Seed a comment for admin delete/moderate check
    db = TestingSessionLocal()
    post = TravelPost(user_id=tourist_id, destination_id="amber", content="Story", moderation_status="approved")
    db.add(post)
    db.flush()
    comment = PostComment(user_id=tourist_id, post_id=post.id, content="Needs review", moderation_status="pending")
    db.add(comment)
    db.commit()
    comment_id = comment.id
    db.close()

    # Provisioned admin logs in
    _create_admin("admin@raahi.gov.in", "AdminPass123")
    admin = TestClient(app)
    login_res = admin.post(
        "/api/auth/login",
        json={"email": "admin@raahi.gov.in", "password": "AdminPass123"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["role"] == "admin"

    # Admin sees pending report and approves it
    pending = admin.get("/api/admin/reports?status_filter=pending")
    assert pending.status_code == 200
    assert any(r["id"] == report["id"] for r in pending.json()["reports"])

    approve = admin.patch(f"/api/admin/reports/{report['id']}", json={"status": "approved"})
    assert approve.status_code == 200
    assert approve.json()["new_status"] == "approved"

    # Tourist rewards reflect authenticated account only
    bal = tourist.get("/api/rewards/balance", headers={"X-User-Id": "forged_other_user"})
    assert bal.status_code == 200
    assert bal.json()["user_id"] == tourist_id
    assert bal.json()["total_points"] == 20

    # Admin verifies and deletes comment
    assert admin.patch(f"/api/admin/comments/{comment_id}", json={"status": "approved"}).status_code == 200
    assert admin.delete(f"/api/admin/comments/{comment_id}").status_code == 200

