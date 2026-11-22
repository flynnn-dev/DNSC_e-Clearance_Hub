"""A signed slip is public to check, masked, and revoked by a later hold."""

import json
import os
import re

import pytest
from dotenv import load_dotenv

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.config import BASE_DIR
from app.db.postgres_repo import connect_postgres
from app.db.users import save_user
from app.importers.accounting_csv import manifest_problem
from app.security.masking import mask_student_number
from app.security.passwords import hash_password
from scripts.seed_users import seed

_NUMBER = "2099-00013"
_EMAIL = "slip-phase13@example.com"
_PASSWORD = "phase13-test-password"
_NAME = "Phase Thirteen"


@pytest.fixture(scope="module")
def app():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    seed(database_url)
    application = create_app()
    application.config["TESTING"] = True
    application.config["SLIP_SIGNING_KEY"] = "phase13-test-signing-key"
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_student_number_is_masked_and_a_manifest_signature_must_be_hex():
    load_dotenv(BASE_DIR / ".env")
    assert mask_student_number("2023-24935") == "2023-***35"
    assert mask_student_number("nope") == "****-*****"
    manifest = json.loads(
        (BASE_DIR / "samples" / "accounting" / "accounting_balances_2026-11-20.csv.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest_problem(manifest, manifest["sha256"], manifest["file"], manifest["record_count"]) is None
    manifest["signature"] = "not-a-signature"
    problem = manifest_problem(manifest, manifest["sha256"], manifest["file"], manifest["record_count"])
    assert problem == "Accounting manifest signature is invalid."


def test_slip_issue_requires_the_student(client):
    assert client.post("/api/me/slip").status_code == 401
    _sign_in(client, os.environ["SEED_STAFF_EMAIL"], os.environ["SEED_STAFF_PASSWORD"])
    denied = client.post("/api/me/slip", headers={"X-CSRF-Token": _csrf(client, "/staff")})
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "You cannot open this page."


def test_cleared_student_gets_a_masked_slip_that_a_hold_revokes(client, app):
    database_url = os.environ["DATABASE_URL"]
    _prepare_student(database_url)
    try:
        _sign_in(client, _EMAIL, _PASSWORD)
        token = _csrf(client, "/student")
        early = client.post("/api/me/slip", headers={"X-CSRF-Token": token})
        assert early.status_code == 409
        _mark_cleared(database_url)
        issued = client.post("/api/me/slip", headers={"X-CSRF-Token": token})
        assert issued.status_code == 200
        body = issued.get_json()
        assert body["qr_svg"].startswith("<svg")
        assert body["verify_path"].startswith("/verify/")
        slip = body["verify_path"].removeprefix("/verify/")
        public = app.test_client()
        checked = public.get(f"/api/verify/{slip}")
        assert checked.status_code == 200
        payload = checked.get_json()
        assert payload["verified"] is True
        assert payload["cleared"] is True
        assert payload["student_number"] == "2099-***13"
        assert _NUMBER not in checked.get_data(as_text=True)
        assert _NAME not in checked.get_data(as_text=True)
        for hidden in ("balance", "fine", "title", "display_name"):
            assert hidden not in payload
        page = public.get(body["verify_path"])
        assert page.status_code == 200
        assert _NUMBER.encode() not in page.data
        tampered = slip[:-1] + ("0" if slip[-1] != "0" else "1")
        assert public.get(f"/api/verify/{tampered}").status_code == 404
        with connect_postgres(database_url) as connection:
            connection.execute(
                """
                UPDATE clearance_tokens
                SET expires_at = now() - interval '1 day'
                WHERE student_id = (SELECT id FROM students WHERE student_number = %s)
                """,
                (_NUMBER,),
            )
            connection.commit()
        expired = public.get(f"/api/verify/{slip}")
        assert expired.status_code == 200
        assert expired.get_json()["status"] == "expired"
        assert expired.get_json()["cleared"] is False
        fresh = client.post("/api/me/slip", headers={"X-CSRF-Token": token})
        assert fresh.status_code == 200
        second = fresh.get_json()["verify_path"].removeprefix("/verify/")
        _sign_in(client, os.environ["SEED_STAFF_EMAIL"], os.environ["SEED_STAFF_PASSWORD"])
        held = client.post(
            f"/api/staff/clearance/{_NUMBER}/hold",
            json={"reason": "Slip test hold"},
            headers={"X-CSRF-Token": _csrf(client, "/staff")},
        )
        assert held.status_code == 200
        revoked = public.get(f"/api/verify/{second}")
        assert revoked.status_code == 200
        assert revoked.get_json()["status"] == "revoked"
        assert revoked.get_json()["cleared"] is False
        assert _NUMBER not in revoked.get_data(as_text=True)
        with connect_postgres(database_url) as connection:
            actions = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT action FROM audit_logs
                    WHERE student_id = (SELECT id FROM students WHERE student_number = %s)
                    """,
                    (_NUMBER,),
                )
            }
        assert "slip_issued" in actions
        assert "slip_revoked" in actions
    finally:
        _delete_test_student(database_url)


def _prepare_student(database_url: str) -> None:
    with connect_postgres(database_url) as connection:
        save_user(connection, _EMAIL, hash_password(_PASSWORD), "student", None)
        user_id = connection.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s)",
            (_EMAIL,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO students (student_number, display_name, user_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (student_number) DO UPDATE
            SET display_name = EXCLUDED.display_name, user_id = EXCLUDED.user_id
            """,
            (_NUMBER, _NAME, user_id),
        )
        connection.commit()


def _mark_cleared(database_url: str) -> None:
    with connect_postgres(database_url) as connection:
        staff_id = connection.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s)",
            (os.environ["SEED_STAFF_EMAIL"],),
        ).fetchone()[0]
        student_id = connection.execute(
            "SELECT id FROM students WHERE student_number = %s",
            (_NUMBER,),
        ).fetchone()[0]
        for office in ("library", "accounting"):
            connection.execute(
                """
                INSERT INTO office_clearance (student_id, office, status, signed_off_by, signed_off_at)
                VALUES (%s, %s, 'CLEARED', %s, now())
                ON CONFLICT (student_id, office) DO UPDATE
                SET status = 'CLEARED',
                    hold_reason = NULL,
                    signed_off_by = EXCLUDED.signed_off_by,
                    signed_off_at = now(),
                    updated_at = now()
                """,
                (student_id, office, staff_id),
            )
        connection.execute(
            """
            INSERT INTO clearance (student_id, overall_status)
            VALUES (%s, 'CLEARED')
            ON CONFLICT (student_id) DO UPDATE
            SET overall_status = 'CLEARED', updated_at = now()
            """,
            (student_id,),
        )
        connection.commit()


def _delete_test_student(database_url: str) -> None:
    with connect_postgres(database_url) as connection:
        student_ids = "(SELECT id FROM students WHERE student_number = %s)"
        connection.execute(f"DELETE FROM clearance_tokens WHERE student_id IN {student_ids}", (_NUMBER,))
        connection.execute(f"DELETE FROM clearance_events WHERE student_id IN {student_ids}", (_NUMBER,))
        connection.execute(f"DELETE FROM audit_logs WHERE student_id IN {student_ids}", (_NUMBER,))
        connection.execute(f"DELETE FROM office_clearance WHERE student_id IN {student_ids}", (_NUMBER,))
        connection.execute(f"DELETE FROM clearance WHERE student_id IN {student_ids}", (_NUMBER,))
        connection.execute("DELETE FROM students WHERE student_number = %s", (_NUMBER,))
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
    page = client.get(path, follow_redirects=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    assert match is not None, page.status_code
    return match.group(1)
