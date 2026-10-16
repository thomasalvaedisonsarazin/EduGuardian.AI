"""Shared test fixtures.

Tests run against a real Postgres database (``TEST_DATABASE_URL``, default ``eduguardian_test``
on the dev container). Each test runs inside a transaction that is rolled back afterwards, so
tests can commit freely without leaking state.

Fixtures:
- ``db``: SQLAlchemy session for the test.
- ``client``: TestClient using ``db``; no auth overrides (use it for real auth flows).
- ``make_tenant(role=..., school=None)``: creates a school (unless given), user and membership
  and returns a ``TenantContext``.
- ``client_as(ctx)``: TestClient whose ``get_current_user``/``get_tenant_context`` resolve to
  ``ctx`` - use it to test module endpoints without going through JWT auth.
"""

import itertools
import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://edu:edu@localhost:5432/eduguardian_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("LLM_ENABLED", "false")

from app.database import Base, get_db  # noqa: E402
from app.dependencies import TenantContext, get_current_user, get_tenant_context  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Membership, MembershipRole, School, User  # noqa: E402

_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
_counter = itertools.count(1)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    yield
    _engine.dispose()


@pytest.fixture()
def db() -> Iterator[Session]:
    connection = _engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_tenant(db: Session) -> Callable[..., TenantContext]:
    def _make(
        role: MembershipRole | str = MembershipRole.school_admin, school: School | None = None
    ) -> TenantContext:
        n = next(_counter)
        if school is None:
            school = School(name=f"Test School {n}", code=f"TS{n:04d}")
            db.add(school)
            db.flush()
        user = User(email=f"user{n}@example.test", hashed_password="x", full_name=f"User {n}")
        db.add(user)
        db.flush()
        db.add(Membership(user_id=user.id, school_id=school.id, role=MembershipRole(role)))
        db.flush()
        return TenantContext(user=user, school_id=school.id, role=MembershipRole(role))

    return _make


@pytest.fixture()
def client_as(db: Session) -> Iterator[Callable[[TenantContext], TestClient]]:
    clients: list[TestClient] = []

    def _client(ctx: TenantContext) -> TestClient:
        # Overrides are global to the app, so the most recent ctx wins; build one client per
        # test step when switching tenants (e.g. cross-tenant isolation tests).
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: ctx.user
        app.dependency_overrides[get_tenant_context] = lambda: ctx
        c = TestClient(app)
        clients.append(c)
        return c

    yield _client
    app.dependency_overrides.clear()
