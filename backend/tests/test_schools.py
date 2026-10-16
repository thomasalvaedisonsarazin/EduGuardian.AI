"""School info and member-management tests (tenant-scoped, school_admin only for writes)."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import auth_rate_limiter
from app.dependencies import TenantContext
from app.models import AuditLog, Membership, MembershipRole, School, User

MakeTenant = Callable[..., TenantContext]
ClientAs = Callable[[TenantContext], TestClient]

BASE = "/api/v1/schools/current"


def _membership_id(db: Session, ctx: TenantContext) -> int:
    mid = db.scalar(
        select(Membership.id).where(
            Membership.user_id == ctx.user.id, Membership.school_id == ctx.school_id
        )
    )
    assert mid is not None
    return mid


def test_current_school(make_tenant: MakeTenant, client_as: ClientAs, db: Session) -> None:
    ctx = make_tenant(MembershipRole.teacher)
    res = client_as(ctx).get(BASE)
    assert res.status_code == 200
    school = db.get(School, ctx.school_id)
    assert school is not None
    assert res.json() == {
        "id": school.id,
        "name": school.name,
        "code": school.code,
        "created_at": res.json()["created_at"],
    }


def test_list_members_only_own_school(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin = make_tenant(MembershipRole.school_admin)
    school = db.get(School, admin.school_id)
    teacher = make_tenant(MembershipRole.teacher, school=school)
    other = make_tenant(MembershipRole.school_admin)  # different school

    res = client_as(teacher).get(f"{BASE}/members")
    assert res.status_code == 200
    emails = {m["email"] for m in res.json()}
    assert emails == {admin.user.email, teacher.user.email}
    assert other.user.email not in emails


def test_add_new_member_generates_temporary_password(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin = make_tenant(MembershipRole.school_admin)
    res = client_as(admin).post(
        f"{BASE}/members",
        json={"email": "New.Teacher@Example.com", "full_name": "New Teacher", "role": "teacher"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "new.teacher@example.com"
    assert body["role"] == "teacher"
    assert body["school_id"] == admin.school_id
    assert body["user_created"] is True
    temp = body["temporary_password"]
    assert isinstance(temp, str) and len(temp) >= 12

    user = db.scalar(select(User).where(User.email == "new.teacher@example.com"))
    assert user is not None and verify_password(temp, user.hashed_password)

    # The new member can log in with the temporary password.
    auth_rate_limiter.reset()
    login = client_as(admin).post(
        "/api/v1/auth/login", json={"email": "new.teacher@example.com", "password": temp}
    )
    assert login.status_code == 200

    audit = db.scalar(
        select(AuditLog).where(
            AuditLog.school_id == admin.school_id,
            AuditLog.action == "member.added",
            AuditLog.entity_id == body["id"],
        )
    )
    assert audit is not None and audit.user_id == admin.user.id


def test_add_member_with_given_password(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin = make_tenant()
    res = client_as(admin).post(
        f"{BASE}/members",
        json={
            "email": "given@example.com",
            "full_name": "Given",
            "role": "coordinator",
            "password": "chosen-pass-1",
        },
    )
    assert res.status_code == 201
    assert res.json()["temporary_password"] is None
    user = db.scalar(select(User).where(User.email == "given@example.com"))
    assert user is not None and verify_password("chosen-pass-1", user.hashed_password)


def test_add_existing_user_and_duplicate(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin = make_tenant()
    other_school_user = make_tenant(MembershipRole.teacher)  # exists in another school
    other_school_user.user.email = "existing.teacher@example.com"
    db.commit()
    client = client_as(admin)
    payload = {"email": other_school_user.user.email, "full_name": "Ignored", "role": "principal"}
    res = client.post(f"{BASE}/members", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["user_created"] is False
    assert body["temporary_password"] is None
    assert body["user_id"] == other_school_user.user.id
    assert body["full_name"] == other_school_user.user.full_name

    dup = client.post(f"{BASE}/members", json=payload)
    assert dup.status_code == 409


def test_add_member_validation(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    client = client_as(make_tenant())
    bad_role = {"email": "a@example.com", "full_name": "A", "role": "janitor"}
    assert client.post(f"{BASE}/members", json=bad_role).status_code == 422
    short_pw = {"email": "a@example.com", "full_name": "A", "role": "teacher", "password": "x"}
    assert client.post(f"{BASE}/members", json=short_pw).status_code == 422


def test_non_admin_cannot_manage_members(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    for role in (MembershipRole.principal, MembershipRole.coordinator, MembershipRole.teacher):
        ctx = make_tenant(role)
        client = client_as(ctx)
        mid = _membership_id(db, ctx)
        new = {"email": f"{role.value}@example.com", "full_name": "X", "role": "teacher"}
        assert client.post(f"{BASE}/members", json=new).status_code == 403
        assert (
            client.patch(f"{BASE}/members/{mid}", json={"role": "school_admin"}).status_code == 403
        )
        assert client.delete(f"{BASE}/members/{mid}").status_code == 403


def test_update_member_role(make_tenant: MakeTenant, client_as: ClientAs, db: Session) -> None:
    admin = make_tenant()
    school = db.get(School, admin.school_id)
    teacher = make_tenant(MembershipRole.teacher, school=school)
    mid = _membership_id(db, teacher)
    res = client_as(admin).patch(f"{BASE}/members/{mid}", json={"role": "coordinator"})
    assert res.status_code == 200
    assert res.json()["role"] == "coordinator"
    membership = db.get(Membership, mid)
    assert membership is not None and membership.role == MembershipRole.coordinator
    assert db.scalar(
        select(AuditLog).where(AuditLog.action == "member.role_changed", AuditLog.entity_id == mid)
    )


def test_cannot_demote_or_remove_last_admin(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin = make_tenant()
    mid = _membership_id(db, admin)
    client = client_as(admin)
    assert client.patch(f"{BASE}/members/{mid}", json={"role": "teacher"}).status_code == 409
    assert client.delete(f"{BASE}/members/{mid}").status_code == 409

    # With a second admin, demotion is allowed.
    school = db.get(School, admin.school_id)
    make_tenant(MembershipRole.school_admin, school=school)
    assert client.patch(f"{BASE}/members/{mid}", json={"role": "teacher"}).status_code == 200


def test_remove_member(make_tenant: MakeTenant, client_as: ClientAs, db: Session) -> None:
    admin = make_tenant()
    school = db.get(School, admin.school_id)
    teacher = make_tenant(MembershipRole.teacher, school=school)
    mid = _membership_id(db, teacher)
    res = client_as(admin).delete(f"{BASE}/members/{mid}")
    assert res.status_code == 204
    assert db.get(Membership, mid) is None
    assert db.get(User, teacher.user.id) is not None  # user account is kept
    assert db.scalar(
        select(AuditLog).where(AuditLog.action == "member.removed", AuditLog.entity_id == mid)
    )
    assert client_as(admin).delete(f"{BASE}/members/{mid}").status_code == 404


def test_cross_tenant_member_access_is_404(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin_a = make_tenant()
    admin_b = make_tenant()
    school_b = db.get(School, admin_b.school_id)
    teacher_b = make_tenant(MembershipRole.teacher, school=school_b)
    foreign_mid = _membership_id(db, teacher_b)

    client = client_as(admin_a)
    patch = client.patch(f"{BASE}/members/{foreign_mid}", json={"role": "principal"})
    assert patch.status_code == 404
    assert client.delete(f"{BASE}/members/{foreign_mid}").status_code == 404
    membership = db.get(Membership, foreign_mid)
    assert membership is not None and membership.role == MembershipRole.teacher


def test_password_hash_helper_roundtrip() -> None:
    hashed = hash_password("abc12345")
    assert hashed.startswith("$2")
    assert verify_password("abc12345", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("abc12345", "not-a-hash")
