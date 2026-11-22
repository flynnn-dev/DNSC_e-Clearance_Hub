"""The Registrar client follows the mock API contract."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR
from app.integrations.registrar_client import RegistrarClient, RegistrarError
from app.services.registrar_sync import sync_masterlist


class _Api:
    def __init__(self, responses):
        self.responses = list(responses)
        handler = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, body, headers = handler.responses.pop(0)
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, fmt, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def test_display_name_uses_the_starter_kit_fields():
    from app.services.registrar_sync import _normalize

    student, reason = _normalize({
        "student_id": "2026-29417",
        "last_name": "Navarro",
        "first_name": "Mark",
        "middle_initial": "D",
    })
    assert reason is None
    assert student["display_name"] == "Mark D Navarro"


def test_client_reads_every_page_and_retries_503():
    api = _Api([
        (503, {"error": "busy"}, {"Retry-After": "0"}),
        (200, {"data": [{"student_id": "2023-59928", "full_name": "Ana Cruz"}], "has_next": True}, {}),
        (200, {"data": [{"student_id": "bad-id"}], "has_next": False}, {}),
    ])
    try:
        rows = RegistrarClient(api.url, "test-key", timeout=2).fetch_masterlist()
    finally:
        api.close()
    assert [row["student_id"] for row in rows] == ["2023-59928", "bad-id"]


def test_client_rejects_a_bad_key_invalid_json_and_a_timeout():
    denied = _Api([(401, {"error": "missing or invalid X-API-Key"}, {})])
    try:
        with pytest.raises(RegistrarError, match="API key"):
            RegistrarClient(denied.url, "wrong", timeout=2).fetch_masterlist()
    finally:
        denied.close()

    broken = _Api([(200, b"not-json", {})])
    try:
        with pytest.raises(RegistrarError, match="invalid JSON"):
            RegistrarClient(broken.url, "test-key", timeout=2).fetch_masterlist()
    finally:
        broken.close()

    stalled = _Api([])

    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            import time
            time.sleep(1)

        def log_message(self, fmt, *args):
            return

    stalled.server.shutdown()
    slow_server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    thread = threading.Thread(target=slow_server.serve_forever, daemon=True)
    thread.start()
    host, port = slow_server.server_address
    try:
        with pytest.raises(RegistrarError, match="timed out"):
            RegistrarClient(f"http://{host}:{port}", "test-key", timeout=0.2).fetch_masterlist()
    finally:
        slow_server.shutdown()
        slow_server.server_close()


def test_sync_stores_valid_students_and_rejects_bad_ids():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    page = (200, {
        "data": [
            {"student_id": "2099-00001", "full_name": "Ana Cruz"},
            {"student_id": "not-a-number", "full_name": "Skipped"},
        ],
        "has_next": False,
    }, {})
    api = _Api([page, page])
    from app.db.postgres_repo import connect_postgres
    try:
        result = sync_masterlist(database_url, api.url, "test-key")
        assert result == {"accepted": 1, "rejected": 1}
        with connect_postgres(database_url) as connection:
            row = connection.execute(
                "SELECT display_name FROM students WHERE student_number = %s",
                ("2099-00001",),
            ).fetchone()
            assert row[0] == "Ana Cruz"
            connection.execute(
                """
                UPDATE office_clearance
                SET status = 'HOLD', hold_reason = 'Unreturned book'
                WHERE office = 'library'
                  AND student_id = (SELECT id FROM students WHERE student_number = %s)
                """,
                ("2099-00001",),
            )
            connection.commit()
        assert sync_masterlist(database_url, api.url, "test-key")["accepted"] == 1
        with connect_postgres(database_url) as connection:
            status = connection.execute(
                """
                SELECT status FROM office_clearance
                WHERE office = 'library'
                  AND student_id = (SELECT id FROM students WHERE student_number = %s)
                """,
                ("2099-00001",),
            ).fetchone()
            assert status[0] == "HOLD"
            connection.execute(
                "DELETE FROM office_clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
                ("2099-00001",),
            )
            connection.execute(
                "DELETE FROM clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
                ("2099-00001",),
            )
            connection.execute("DELETE FROM students WHERE student_number = %s", ("2099-00001",))
            connection.execute(
                "DELETE FROM rejected_records WHERE student_number = %s",
                ("not-a-number",),
            )
            connection.execute(
                """
                DELETE FROM import_logs
                WHERE source = 'registrar_api'
                  AND message = 'Masterlist synced.'
                  AND NOT EXISTS (
                      SELECT 1 FROM rejected_records WHERE import_log_id = import_logs.id
                  )
                """
            )
            connection.commit()
    finally:
        api.close()
