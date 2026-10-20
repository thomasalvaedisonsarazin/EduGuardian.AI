"""Hardening needed before the app is exposed on the internet."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agents.data_quality import parse_marks_file
from app.auth.rate_limit import auth_rate_limiter, login_account_limiter
from app.config import settings
from app.exceptions import DomainValidationError
from app.services.setup_service import parse_tabular

REGISTER = {
    "email": "harden@example.com",
    "password": "Str0ng-pass!",
    "full_name": "Hard Ening",
    "school_name": "Hardening School",
}


@pytest.fixture(autouse=True)
def _reset_limits() -> Iterator[None]:
    auth_rate_limiter.reset()
    login_account_limiter.reset()
    yield
    auth_rate_limiter.reset()
    login_account_limiter.reset()


def test_registration_can_be_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    res = client.post("/api/v1/auth/register", json=REGISTER)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "REGISTRATION_DISABLED"


def test_refresh_token_cookie_flow(client: TestClient) -> None:
    res = client.post("/api/v1/auth/register", json=REGISTER)
    assert res.status_code == 201
    set_cookie = res.headers["set-cookie"]
    assert f"{settings.REFRESH_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "samesite=strict" in set_cookie.lower()

    # No body: the cookie alone refreshes the session and rotates the token.
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    # Logout via cookie revokes the token and clears the cookie.
    old_cookie = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.cookies.get(settings.REFRESH_COOKIE_NAME) is None
    assert old_cookie
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": old_cookie})
    assert again.status_code == 401


def test_refresh_without_any_token_is_401(client: TestClient) -> None:
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_login_limited_per_account_across_ips(client: TestClient) -> None:
    payload = {"email": "Target@Example.com", "password": "wrong"}
    for _ in range(10):
        auth_rate_limiter.reset()  # simulate attempts arriving from different IPs
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
    auth_rate_limiter.reset()
    blocked = client.post("/api/v1/auth/login", json={**payload, "email": "target@example.com"})
    assert blocked.status_code == 429
    # Another account is unaffected.
    other = client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "y"})
    assert other.status_code == 401


def test_marks_file_row_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_IMPORT_ROWS", 3)
    ok = b"admission_no,English\n" + b"".join(f"A{i},50\n".encode() for i in range(3))
    assert len(parse_marks_file(ok, "m.csv").rows) == 3
    big = b"admission_no,English\n" + b"".join(f"A{i},50\n".encode() for i in range(4))
    with pytest.raises(DomainValidationError) as info:
        parse_marks_file(big, "m.csv")
    assert info.value.code == "TOO_MANY_ROWS"


def test_student_file_row_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_IMPORT_ROWS", 3)
    ok = b"admission_no,full_name\n" + b"".join(f"A{i},N{i}\n".encode() for i in range(3))
    assert len(parse_tabular(ok, "s.csv")) == 3
    big = b"admission_no,full_name\n" + b"".join(f"A{i},N{i}\n".encode() for i in range(4))
    with pytest.raises(DomainValidationError) as info:
        parse_tabular(big, "s.csv")
    assert info.value.code == "TOO_MANY_ROWS"
