"""Working days skip weekends and Philippine holidays, and stop when the calendar is missing."""

import json
import os
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR
from app.integrations.holiday_client import HolidayClient, HolidayError
from app.services.deadline_service import DeadlineUnavailable, add_working_days, clearance_deadline, deadline_after


def test_working_days_skip_weekends_and_a_holiday():
    holidays = {date(2026, 11, 30)}
    assert add_working_days(date(2026, 11, 20), 5, holidays) == date(2026, 11, 27)
    assert add_working_days(date(2026, 11, 27), 1, holidays) == date(2026, 12, 1)


def test_client_reads_a_public_holiday_list():
    server = _Api([(200, [{
        "date": "2026-11-30",
        "localName": "Bonifacio Day",
        "name": "Bonifacio Day",
        "types": ["Public"],
    }])])
    try:
        rows = HolidayClient(timeout=2, base_url=server.url).fetch_year(2026)
    finally:
        server.close()
    assert rows == [{"date": date(2026, 11, 30), "local_name": "Bonifacio Day", "name": "Bonifacio Day"}]


def test_a_failed_lookup_uses_the_saved_year_and_refuses_an_empty_year():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    from app.db.postgres_repo import connect_postgres

    class Down(HolidayClient):
        def fetch_year(self, year: int):
            raise HolidayError("down")

    start = date(2099, 6, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)
    holiday = start + timedelta(days=1)
    with connect_postgres(database_url) as connection:
        connection.execute("DELETE FROM holiday_fetch_logs WHERE calendar_year IN (2098, 2099)")
        connection.execute(
            "DELETE FROM public_holidays WHERE holiday_date >= %s AND holiday_date < %s",
            (date(2098, 1, 1), date(2100, 1, 1)),
        )
        connection.execute(
            """
            INSERT INTO public_holidays (holiday_date, local_name, name)
            VALUES (%s, 'Test Holiday', 'Test Holiday')
            """,
            (holiday,),
        )
        connection.execute(
            """
            INSERT INTO holiday_fetch_logs (calendar_year, status, message)
            VALUES (2099, 'accepted', 'test save')
            """
        )
        connection.commit()
    try:
        assert deadline_after(database_url, start, 1, Down()) == holiday + timedelta(days=1)
        with pytest.raises(DeadlineUnavailable):
            deadline_after(database_url, date(2098, 6, 1), 1, Down())
    finally:
        with connect_postgres(database_url) as connection:
            connection.execute(
                "DELETE FROM public_holidays WHERE holiday_date >= %s AND holiday_date < %s",
                (date(2098, 1, 1), date(2100, 1, 1)),
            )
            connection.execute("DELETE FROM holiday_fetch_logs WHERE calendar_year IN (2098, 2099)")
            connection.commit()


def test_clearance_deadline_needs_a_setting_before_it_looks_up_holidays():
    result = clearance_deadline("", "not-a-date", "5")
    assert result["deadline"] is None
    assert result["deadline_error"] == "The clearance deadline is not configured."


def test_clearance_deadline_uses_saved_holidays_and_refuses_a_missing_year():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    from app.db.postgres_repo import connect_postgres

    class Down(HolidayClient):
        def fetch_year(self, year: int):
            raise HolidayError("down")

    start = date(2099, 6, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)
    holiday = start + timedelta(days=1)
    expected = holiday + timedelta(days=1)
    with connect_postgres(database_url) as connection:
        connection.execute("DELETE FROM holiday_fetch_logs WHERE calendar_year IN (2098, 2099)")
        connection.execute(
            "DELETE FROM public_holidays WHERE holiday_date >= %s AND holiday_date < %s",
            (date(2098, 1, 1), date(2100, 1, 1)),
        )
        connection.execute(
            """
            INSERT INTO public_holidays (holiday_date, local_name, name)
            VALUES (%s, 'Test Holiday', 'Test Holiday')
            """,
            (holiday,),
        )
        connection.execute(
            """
            INSERT INTO holiday_fetch_logs (calendar_year, status, message)
            VALUES (2099, 'accepted', 'test save')
            """
        )
        connection.commit()
    try:
        saved = clearance_deadline(database_url, start.isoformat(), "1", Down())
        missing = clearance_deadline(database_url, "2098-06-01", "1", Down())
    finally:
        with connect_postgres(database_url) as connection:
            connection.execute(
                "DELETE FROM public_holidays WHERE holiday_date >= %s AND holiday_date < %s",
                (date(2098, 1, 1), date(2100, 1, 1)),
            )
            connection.execute("DELETE FROM holiday_fetch_logs WHERE calendar_year IN (2098, 2099)")
            connection.commit()
    assert saved == {"deadline": expected.isoformat(), "deadline_error": None}
    assert missing["deadline"] is None
    assert missing["deadline_error"] == "The clearance deadline is unavailable because the holiday list could not be loaded."


class _Api:
    def __init__(self, responses):
        self.responses = list(responses)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, body = self.server.responses.pop(0)
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, fmt, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.responses = self.responses
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
