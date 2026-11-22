"""Staff can hold or sign off their own office. A student sees only the linked record."""

import os
import re

import pytest
from dotenv import load_dotenv
from psycopg.types.json import Json

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.config import BASE_DIR
from app.db.postgres_repo import connect_postgres
from app.db.users import save_user
from app.security.passwords import hash_password
from scripts.seed_users import seed

_NUMBER = "2099-00021"
_EMAIL = "clearance-phase10@example.com"
_PASSWORD = "phase10-test-password"


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


def test_student_sees_only_the_linked_record_and_cannot_act_as_staff(client):
    database_url = os.environ["DATABASE_URL"]
    with connect_postgres(database_url) as connection:
        save_user(connection, _EMAIL, hash_password(_PASSWORD), "student", None)
        user_id = connection.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s)",
            (_EMAIL,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO students (student_number, display_name, user_id, registrar_payload)
            VALUES (%s, 'Phase Ten', %s, %s)
            ON CONFLICT (student_number) DO UPDATE
            SET display_name = EXCLUDED.display_name, user_id = EXCLUDED.user_id
            """,
            (_NUMBER, user_id, Json({"program_name": "Test Program"})),
        )
        connection.commit()
    try:
        _sign_in(client, _EMAIL, _PASSWORD)
        ignored = client.get("/api/me/clearance?student_id=2026-29417")
        assert ignored.status_code == 200
        body = ignored.get_json()
        assert body["linked"] is True
        assert body["student_number"] == _NUMBER
        assert body["program"] == "Test Program"
        assert client.get("/api/staff/clearance").status_code == 403
        token = _csrf(client, "/student")
        denied = client.post(
            f"/api/staff/clearance/{_NUMBER}/signoff",
            headers={"X-CSRF-Token": token},
        )
        assert denied.status_code == 403
    finally:
        _delete_test_student(database_url)


def test_staff_signoff_stops_for_a_blocking_record_and_a_hold_clears_it(client):
    database_url = os.environ["DATABASE_URL"]
    with connect_postgres(database_url) as connection:
        connection.execute(
            "INSERT INTO students (student_number, display_name) VALUES (%s, 'Hold Test') ON CONFLICT (student_number) DO NOTHING",
            (_NUMBER,),
        )
        connection.commit()
    try:
        _sign_in(client, os.environ["SEED_STAFF_EMAIL"], os.environ["SEED_STAFF_PASSWORD"])
        token = _csrf(client, "/staff")
        missing = client.post(
            f"/api/staff/clearance/{_NUMBER}/hold",
            json={"reason": "   "},
            headers={"X-CSRF-Token": token},
        )
        assert missing.status_code == 400
        signed = client.post(
            f"/api/staff/clearance/{_NUMBER}/signoff",
            headers={"X-CSRF-Token": token},
        )
        assert signed.status_code == 200
        assert signed.get_json()["status"] == "CLEARED"
        with connect_postgres(database_url) as connection:
            student_id = connection.execute(
                "SELECT id FROM students WHERE student_number = %s",
                (_NUMBER,),
            ).fetchone()[0]
            log_id = connection.execute(
                """
                INSERT INTO import_logs (source, status, message)
                VALUES ('library_xml', 'accepted', 'phase10-test')
                RETURNING id
                """
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO library_records (
                    student_id, import_log_id, title, is_unreturned, fine_cents, is_blocking, source_payload
                )
                VALUES (%s, %s, '1 unreturned book', TRUE, 0, TRUE, %s)
                """,
                (student_id, log_id, Json({})),
            )
            connection.commit()
        blocked = client.post(
            f"/api/staff/clearance/{_NUMBER}/signoff",
            headers={"X-CSRF-Token": token},
        )
        assert blocked.status_code == 409
        held = client.post(
            f"/api/staff/clearance/{_NUMBER}/hold",
            json={"reason": "Missing book"},
            headers={"X-CSRF-Token": token},
        )
        assert held.status_code == 200
        with connect_postgres(database_url) as connection:
            row = connection.execute(
                """
                SELECT office_clearance.status, office_clearance.hold_reason, clearance.overall_status
                FROM students
                JOIN office_clearance ON office_clearance.student_id = students.id AND office_clearance.office = 'library'
                JOIN clearance ON clearance.student_id = students.id
                WHERE students.student_number = %s
                """,
                (_NUMBER,),
            ).fetchone()
            assert row == ("HOLD", "Missing book", "HOLD")
        queue = client.get("/api/staff/clearance")
        assert queue.status_code == 200
        assert queue.get_json()["office"] == "library"
        listed = next(item for item in queue.get_json()["students"] if item["student_number"] == _NUMBER)
        assert listed["blocking"] is True
        assert listed["status"] == "HOLD"
    finally:
        _delete_test_student(database_url)


def test_clearance_api_requires_sign_in(client):
    assert client.get("/api/me/clearance").status_code == 401
    assert client.get("/api/staff/clearance").status_code == 401


def _delete_test_student(database_url: str) -> None:
    with connect_postgres(database_url) as connection:
        connection.execute(
            "DELETE FROM clearance_tokens WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM library_records WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM clearance_events WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM audit_logs WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM office_clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute("DELETE FROM students WHERE student_number = %s", (_NUMBER,))
        connection.execute("DELETE FROM import_logs WHERE message = 'phase10-test'")
        connection.execute("DELETE FROM users WHERE lower(email) = lower(%s)", (_EMAIL,))
        connection.commit()


def _sign_in(client, email: str, password: str) -> None:
    token = _csrf(client)
    response = client.post(
        "/api/auth/login",
        data={"email": email, "password": password, "csrf_token": token},
    )
    assert response.status_code == 302


def _csrf(client, path: str = "/login") -> str:
    page = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page)
    assert match is not None
    return match.group(1)
