"""Auth flow tests: register, login, refresh rotation, logout, /me, token validation, rate limit,
and X-School-Id tenant resolution."""

import itertools
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, hash_refresh_token
from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import auth_rate_limiter, login_account_limiter
from app.models import AuditLog, Membership, MembershipRole, RefreshToken, School, User

PASSWORD = "s3cret-pass"
_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Iterator[None]:
    auth_rate_limiter.reset()
    login_account_limiter.reset()
    yield
    auth_rate_limiter.reset()
    login_account_limiter.reset()


def _email() -> str:
    return f"auth{next(_seq)}@example.com"


def _register(client: TestClient, **overrides: str) -> dict[str, str]:
    payload = {
        "email": _email(),
        "password": PASSWORD,
        "full_name": "Asha Rao",
        "school_name": "Green Valley High",
    }
    payload.update(overrides)
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    body: dict[str, str] = res.json()
    return body


def _bearer(token: str, school_id: int | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if school_id is not None:
        headers["X-School-Id"] = str(school_id)
    return headers


def _make_user(db: Session, *, active: bool = True, superadmin: bool = False) -> User:
    user = User(
        email=_email(),
        hashed_password=hash_password(PASSWORD),
        full_name="Real User",
        is_active=active,
        is_superadmin=superadmin,
    )
    db.add(user)
    db.flush()
    return user


def _make_school(db: Session) -> School:
    n = next(_seq)
    school = School(name=f"School {n}", code=f"AUTHS{n}")
    db.add(school)
    db.flush()
    return school


# --- register ---------------------------------------------------------------------------------


def test_register_creates_user_school_and_admin_membership(client: TestClient, db: Session) -> None:
    email = _email()
    tokens = _register(client, email=email.upper())
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]

    me = client.get("/api/v1/auth/me", headers=_bearer(tokens["access_token"]))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == email  # normalised to lower case
    assert body["is_superadmin"] is False
    assert len(body["memberships"]) == 1
    membership = body["memberships"][0]
    assert membership["role"] == "school_admin"
    assert membership["school"]["name"] == "Green Valley High"
    assert membership["school"]["code"].startswith("GREEN-VALLEY-HIGH")

    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.hashed_password != PASSWORD
    assert verify_password(PASSWORD, user.hashed_password)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert stored is not None
    assert stored.token_hash == hash_refresh_token(tokens["refresh_token"])
    assert db.scalar(
        select(AuditLog).where(
            AuditLog.school_id == membership["school_id"], AuditLog.action == "school.registered"
        )
    )


def test_register_generates_unique_codes_for_same_school_name(
    client: TestClient, db: Session
) -> None:
    _register(client, school_name="Twin Oaks School")
    _register(client, school_name="Twin Oaks School")
    codes = db.scalars(select(School.code).where(School.name == "Twin Oaks School")).all()
    assert len(codes) == 2
    assert len(set(codes)) == 2


def test_register_with_explicit_code_and_duplicate_code(client: TestClient, db: Session) -> None:
    _register(client, school_code="dps-01")
    assert db.scalar(select(School).where(School.code == "DPS-01")) is not None
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": _email(),
            "password": PASSWORD,
            "full_name": "B",
            "school_name": "Other",
            "school_code": "DPS-01",
        },
    )
    assert res.status_code == 409


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    email = _email()
    _register(client, email=email)
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "X", "school_name": "Another"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


@pytest.mark.parametrize(
    "override",
    [{"password": "short"}, {"email": "not-an-email"}, {"school_name": ""}, {"full_name": "  "}],
)
def test_register_validation(client: TestClient, override: dict[str, str]) -> None:
    payload = {
        "email": _email(),
        "password": PASSWORD,
        "full_name": "Asha",
        "school_name": "School",
    }
    payload.update(override)
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422


# --- login ------------------------------------------------------------------------------------


def test_login_success(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    res = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert res.status_code == 200
    me = client.get("/api/v1/auth/me", headers=_bearer(res.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == user.id
    assert me.json()["memberships"] == []


def test_login_is_case_insensitive_on_email(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    res = client.post(
        "/api/v1/auth/login", json={"email": user.email.upper(), "password": PASSWORD}
    )
    assert res.status_code == 200


def test_login_bad_credentials_are_generic(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    wrong_pw = client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope!"})
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_login_inactive_user_rejected(client: TestClient, db: Session) -> None:
    user = _make_user(db, active=False)
    res = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert res.status_code == 401


# --- refresh / logout -------------------------------------------------------------------------


def test_refresh_rotates_and_detects_reuse(client: TestClient, db: Session) -> None:
    first = _register(client)
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert res.status_code == 200
    second = res.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert client.get("/api/v1/auth/me", headers=_bearer(second["access_token"])).status_code == 200

    old = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(first["refresh_token"])
        )
    )
    assert old is not None and old.revoked

    # Reusing the rotated token fails and revokes the whole family (including `second`).
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert after.status_code == 401


def test_refresh_expired_token_rejected(client: TestClient, db: Session) -> None:
    tokens = _register(client)
    stored = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"])
        )
    )
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401


def test_refresh_unknown_token_rejected(client: TestClient) -> None:
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "made-up"})
    assert res.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    tokens = _register(client)
    res = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 204
    again = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 204  # idempotent
    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


# --- access token validation ------------------------------------------------------------------


def test_me_requires_token(client: TestClient) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_tampered_and_invalid_tokens_rejected(client: TestClient) -> None:
    tokens = _register(client)
    access = tokens["access_token"]
    header, payload, signature = access.split(".")
    tampered_sig = f"{header}.{payload}.{signature[:-2]}{'A' if signature[-2] != 'A' else 'B'}x"
    for bad in (tampered_sig, "garbage", tokens["refresh_token"]):
        res = client.get("/api/v1/auth/me", headers=_bearer(bad))
        assert res.status_code == 401, bad


def test_expired_access_token_rejected(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    token = create_access_token(user.id, expires_delta=timedelta(seconds=-5))
    assert client.get("/api/v1/auth/me", headers=_bearer(token)).status_code == 401


def test_token_of_deactivated_user_rejected(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    token = create_access_token(user.id)
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=_bearer(token)).status_code == 401


# --- tenant resolution (X-School-Id) ----------------------------------------------------------


def test_single_membership_resolves_without_header(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    school = _make_school(db)
    db.add(Membership(user_id=user.id, school_id=school.id, role=MembershipRole.teacher))
    db.commit()
    res = client.get("/api/v1/schools/current", headers=_bearer(create_access_token(user.id)))
    assert res.status_code == 200
    assert res.json()["id"] == school.id


def test_multiple_memberships_require_header(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    a, b = _make_school(db), _make_school(db)
    db.add_all(
        [
            Membership(user_id=user.id, school_id=a.id, role=MembershipRole.teacher),
            Membership(user_id=user.id, school_id=b.id, role=MembershipRole.principal),
        ]
    )
    db.commit()
    token = create_access_token(user.id)
    missing = client.get("/api/v1/schools/current", headers=_bearer(token))
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "SCHOOL_REQUIRED"
    chosen = client.get("/api/v1/schools/current", headers=_bearer(token, b.id))
    assert chosen.status_code == 200
    assert chosen.json()["id"] == b.id


def test_header_for_foreign_school_is_404(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    mine, other = _make_school(db), _make_school(db)
    db.add(Membership(user_id=user.id, school_id=mine.id, role=MembershipRole.school_admin))
    db.commit()
    token = create_access_token(user.id)
    res = client.get("/api/v1/schools/current", headers=_bearer(token, other.id))
    assert res.status_code == 404
    res = client.get("/api/v1/schools/current", headers=_bearer(token, 987654))
    assert res.status_code == 404


def test_superadmin_can_access_any_school(client: TestClient, db: Session) -> None:
    admin = _make_user(db, superadmin=True)
    school = _make_school(db)
    db.commit()
    token = create_access_token(admin.id)
    res = client.get("/api/v1/schools/current", headers=_bearer(token, school.id))
    assert res.status_code == 200
    # Superadmin acts as school_admin, so admin-only endpoints work too.
    members = client.get("/api/v1/schools/current/members", headers=_bearer(token, school.id))
    assert members.status_code == 200
    assert client.get("/api/v1/schools/current", headers=_bearer(token, 987654)).status_code == 404


def test_role_enforcement_with_real_tokens(client: TestClient, db: Session) -> None:
    teacher = _make_user(db)
    school = _make_school(db)
    db.add(Membership(user_id=teacher.id, school_id=school.id, role=MembershipRole.teacher))
    db.commit()
    res = client.post(
        "/api/v1/schools/current/members",
        headers=_bearer(create_access_token(teacher.id), school.id),
        json={"email": _email(), "full_name": "New", "role": "teacher"},
    )
    assert res.status_code == 403


# --- rate limiting ----------------------------------------------------------------------------


def test_login_rate_limited(client: TestClient) -> None:
    payload = {"email": "ghost@example.com", "password": "whatever"}
    statuses = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(10)]
    assert statuses == [401] * 10
    blocked = client.post("/api/v1/auth/login", json=payload)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    auth_rate_limiter.reset()
    login_account_limiter.reset()
    assert client.post("/api/v1/auth/login", json=payload).status_code == 401


def test_register_rate_limited_separately(client: TestClient) -> None:
    bad = {"email": "x", "password": "y", "full_name": "z", "school_name": "w"}
    for _ in range(10):
        client.post("/api/v1/auth/register", json=bad)
    assert client.post("/api/v1/auth/register", json=bad).status_code == 429
    # Login has its own bucket.
    login = client.post("/api/v1/auth/login", json={"email": "a@b.co", "password": "p"})
    assert login.status_code == 401
