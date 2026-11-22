"""Sign-in, sign-out, and role checks against Supabase."""

import os
import re

import pytest
from dotenv import load_dotenv

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.config import BASE_DIR
from scripts.seed_users import seed


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


def test_student_cannot_open_staff_pages(client):
    _sign_in(client, "SEED_STUDENT_EMAIL", "SEED_STUDENT_PASSWORD")
    student = client.get("/student")
    assert student.status_code == 200
    assert os.environ["SEED_STUDENT_EMAIL"] in student.get_data(as_text=True)
    assert os.environ["SEED_STUDENT_PASSWORD"] not in student.get_data(as_text=True)
    assert client.get("/staff").status_code == 403
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["role"] == "student"


def test_staff_cannot_open_student_pages(client):
    _sign_in(client, "SEED_STAFF_EMAIL", "SEED_STAFF_PASSWORD")
    staff = client.get("/staff")
    assert staff.status_code == 200
    assert "Library staff" in staff.get_data(as_text=True)
    assert client.get("/student").status_code == 403
    assert client.get("/api/auth/me").get_json()["office"] == "library"


def test_wrong_password_does_not_sign_in(client):
    token = _csrf(client)
    response = client.post(
        "/api/auth/login",
        data={
            "email": os.environ["SEED_STUDENT_EMAIL"],
            "password": "not-the-password",
            "csrf_token": token,
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 401
    assert "incorrect" in page
    assert "not-the-password" not in page
    assert client.get("/student", follow_redirects=False).status_code == 302


def test_injected_email_does_not_sign_in(client):
    token = _csrf(client)
    response = client.post(
        "/api/auth/login",
        data={
            "email": "' OR 1=1 --",
            "password": "' OR '1'='1",
            "csrf_token": token,
        },
    )
    assert response.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_without_csrf_is_rejected(client):
    response = client.post(
        "/api/auth/login",
        data={
            "email": os.environ["SEED_STUDENT_EMAIL"],
            "password": os.environ["SEED_STUDENT_PASSWORD"],
        },
    )
    assert response.status_code == 400
    assert client.get("/api/auth/me").status_code == 401


def test_logout_ends_the_session(client):
    _sign_in(client, "SEED_STUDENT_EMAIL", "SEED_STUDENT_PASSWORD")
    token = _csrf(client, "/student")
    response = client.post("/api/auth/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert client.get("/api/auth/me").status_code == 401


def _sign_in(client, email_key: str, password_key: str) -> None:
    token = _csrf(client)
    response = client.post(
        "/api/auth/login",
        data={
            "email": os.environ[email_key],
            "password": os.environ[password_key],
            "csrf_token": token,
        },
    )
    assert response.status_code == 302


def _csrf(client, path: str = "/login") -> str:
    page = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page)
    assert match is not None
    return match.group(1)
