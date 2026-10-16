from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}


def test_tenant_fixture(make_tenant, client_as) -> None:  # type: ignore[no-untyped-def]
    ctx = make_tenant()
    assert ctx.school_id > 0
    assert client_as(ctx).get("/health").status_code == 200
