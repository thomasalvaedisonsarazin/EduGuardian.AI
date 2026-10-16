"""Bulk student import (CSV / XLSX) tests."""

import io
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.dependencies import TenantContext

ClientAs = Callable[[TenantContext], TestClient]
MakeTenant = Callable[..., TenantContext]


def _prepare(api: TestClient) -> int:
    year = api.post("/api/v1/academic-years", json={"label": "2026-27", "is_current": True}).json()
    old = api.post("/api/v1/academic-years", json={"label": "2025-26"}).json()
    for section in ("A", "B"):
        api.post(
            "/api/v1/classes",
            json={"academic_year_id": year["id"], "grade": 10, "section": section},
        )
    # a class in a non-current year must not be matched
    api.post("/api/v1/classes", json={"academic_year_id": old["id"], "grade": 9, "section": "A"})
    return int(year["id"])


def _upload(api: TestClient, content: bytes, name: str = "students.csv") -> Any:
    return api.post("/api/v1/students/import", files={"file": (name, content, "text/csv")})


def test_import_csv_happy_path_and_upsert(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    api = client_as(make_tenant())
    _prepare(api)
    csv_text = (
        "Admission No,Full Name,Grade,Section\n"
        "GPS1,Asha Rao,10,A\n"
        "GPS2,Vikram Singh,10,b\n"
        "\n"
        "GPS3,Neha Gupta,10,A\n"
    )
    resp = _upload(api, csv_text.encode())
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created": 3, "updated": 0, "errors": []}
    students = api.get("/api/v1/students").json()
    assert students["total"] == 3
    assert sorted(s["pseudo_id"] for s in students["items"]) == ["S-0001", "S-0002", "S-0003"]

    # re-import: upsert by admission number (moves GPS1 to section B, renames)
    resp = _upload(api, b"admission_no,full_name,grade,section\nGPS1,Asha R.,10,B\nGPS4,New,10,A\n")
    assert resp.json() == {"created": 1, "updated": 1, "errors": []}
    asha = api.get("/api/v1/students", params={"q": "GPS1"}).json()["items"][0]
    assert asha["full_name"] == "Asha R." and asha["pseudo_id"] == "S-0001"
    classes = {c["section"]: c for c in api.get("/api/v1/classes").json() if c["grade"] == 10}
    assert asha["class_section_id"] == classes["B"]["id"]


def test_import_reports_row_errors(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    api = client_as(make_tenant())
    _prepare(api)
    csv_text = (
        "admission_no,full_name,grade,section\n"
        "GPS1,Asha,10,A\n"  # row 2 ok
        ",No Admission,10,A\n"  # row 3
        "GPS3,,10,A\n"  # row 4
        "GPS4,Bad Grade,ten,A\n"  # row 5
        "GPS5,No Class,10,Z\n"  # row 6
        "GPS6,Old Year,9,A\n"  # row 7 (class only in non-current year)
        "GPS1,Duplicate,10,A\n"  # row 8
    )
    body = _upload(api, csv_text.encode()).json()
    assert body["created"] == 1 and body["updated"] == 0
    errors = {e["row"]: e["message"] for e in body["errors"]}
    assert set(errors) == {3, 4, 5, 6, 7, 8}
    assert "admission_no is required" in errors[3]
    assert "full_name is required" in errors[4]
    assert "not a number" in errors[5]
    assert "10-Z does not exist" in errors[6]
    assert "9-A does not exist" in errors[7]
    assert "duplicate" in errors[8]


def test_import_xlsx(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    api = client_as(make_tenant())
    _prepare(api)
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["admission_no", "full_name", "grade", "section"])
    ws.append(["X1", "Excel Kid", 10, "A"])
    ws.append([1002, "Numeric Adm", 10.0, "B"])
    buf = io.BytesIO()
    wb.save(buf)
    resp = api.post(
        "/api/v1/students/import",
        files={"file": ("students.xlsx", buf.getvalue(), "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 2
    assert api.get("/api/v1/students", params={"q": "1002"}).json()["total"] == 1


def test_import_file_level_errors(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    api = client_as(make_tenant())
    # no current academic year
    assert _upload(api, b"admission_no,full_name,grade,section\nA,B,10,A\n").status_code == 422
    _prepare(api)
    missing = _upload(api, b"admission_no,full_name\nA,B\n")
    assert missing.status_code == 422
    assert "grade" in missing.json()["error"]["message"]
    assert _upload(api, b"x", name="students.pdf").status_code == 422


def test_import_requires_editor_role(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    api = client_as(make_tenant("teacher"))
    assert _upload(api, b"admission_no,full_name,grade,section\n").status_code == 403
