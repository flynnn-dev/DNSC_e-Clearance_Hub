"""Staff reports mask student numbers. A student cannot download them."""

import os
import re
from urllib.parse import quote

import pytest
from dotenv import load_dotenv

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.config import BASE_DIR
from scripts.seed_users import seed

_FULL_NUMBER = re.compile(r"\d{4}-\d{5}")


@pytest.fixture(scope="module")
def app():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    seed(database_url)
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_reports_mask_ids_and_ignore_a_requested_office(client):
    assert client.get("/api/office/reports.json").status_code == 401
    assert client.get("/api/office/reports.csv").status_code == 401
    _sign_in(client, os.environ["SEED_STUDENT_EMAIL"], os.environ["SEED_STUDENT_PASSWORD"])
    assert client.get("/api/office/reports.json").status_code == 403
    _sign_in(client, os.environ["SEED_STAFF_EMAIL"], os.environ["SEED_STAFF_PASSWORD"])
    injected = client.post(
        "/api/staff/clearance/" + quote("2026-29417' OR 1=1", safe="") + "/hold",
        json={"reason": "injection"},
        headers={"X-CSRF-Token": _csrf(client, "/staff")},
    )
    assert injected.status_code == 404
    report = client.get("/api/office/reports.json?office=accounting")
    assert report.status_code == 200
    body = report.get_json()
    assert body["office"] == "library"
    assert body["students"]
    assert all("***" in item["student_number"] for item in body["students"])
    assert _FULL_NUMBER.search(report.get_data(as_text=True)) is None
    downloaded = client.get("/api/office/reports.csv?office=accounting")
    assert downloaded.status_code == 200
    assert downloaded.mimetype == "text/csv"
    assert "library-clearance.csv" in downloaded.headers["Content-Disposition"]
    text = downloaded.get_data(as_text=True)
    assert text.startswith("student_number,display_name,status,reason\n")
    assert _FULL_NUMBER.search(text) is None
    assert "***" in text


def _sign_in(client, email: str, password: str) -> None:
    token = _csrf(client)
    response = client.post(
        "/api/auth/login",
        data={"email": email, "password": password, "csrf_token": token},
    )
    assert response.status_code == 302


def _csrf(client, path: str = "/login") -> str:
    page = client.get(path, follow_redirects=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    assert match is not None, page.status_code
    return match.group(1)
