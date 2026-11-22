"""Add working days, skipping weekends and saved Philippine holidays."""

from datetime import date, timedelta

from app.db.postgres_repo import connect_postgres
from app.integrations.holiday_client import HolidayClient, HolidayError


class DeadlineUnavailable(Exception):
    """The deadline was not calculated because the holiday list is missing."""


def add_working_days(start: date, working_days: int, holidays: set[date]) -> date:
    if working_days < 0:
        raise DeadlineUnavailable("Working days cannot be negative.")
    current = start
    remaining = working_days
    while remaining:
        current += timedelta(days=1)
        if current.weekday() >= 5 or current in holidays:
            continue
        remaining -= 1
    return current


_UNAVAILABLE = "The clearance deadline is unavailable because the holiday list could not be loaded."
_NOT_CONFIGURED = "The clearance deadline is not configured."


def clearance_deadline(database_url: str, anchor_text: str, days_text: str, client: HolidayClient | None = None) -> dict:
    """Return the configured deadline. A missing holiday list does not invent a date."""
    try:
        anchor = date.fromisoformat(str(anchor_text).strip())
        working_days = int(str(days_text).strip())
    except (TypeError, ValueError):
        return {"deadline": None, "deadline_error": _NOT_CONFIGURED}
    if working_days < 0:
        return {"deadline": None, "deadline_error": _NOT_CONFIGURED}
    try:
        found = deadline_after(database_url, anchor, working_days, client)
    except DeadlineUnavailable:
        return {"deadline": None, "deadline_error": _UNAVAILABLE}
    return {"deadline": found.isoformat(), "deadline_error": None}


def deadline_after(database_url: str, start: date, working_days: int, client: HolidayClient | None = None) -> date:
    if working_days < 0:
        raise DeadlineUnavailable("Working days cannot be negative.")
    calendar = client or HolidayClient()
    years = _years_for(start, working_days)
    holidays: set[date] = set()
    for year in years:
        holidays.update(_holidays_for_year(database_url, year, calendar))
    return add_working_days(start, working_days, holidays)


def _years_for(start: date, working_days: int) -> list[int]:
    span = max(working_days, 0) * 2 + 14
    end = start + timedelta(days=span)
    return list(range(start.year, end.year + 1))


def _holidays_for_year(database_url: str, year: int, client: HolidayClient) -> set[date]:
    try:
        fetched = client.fetch_year(year)
    except HolidayError as exc:
        saved = _saved_dates(database_url, year)
        _log(database_url, year, "failed", str(exc))
        if not _year_was_saved(database_url, year):
            raise DeadlineUnavailable(
                f"Philippine holidays for {year} are unavailable, so the deadline was not calculated."
            ) from exc
        return saved
    _replace_year(database_url, year, fetched)
    _log(database_url, year, "accepted", f"Saved {len(fetched)} public holidays.")
    return {item["date"] for item in fetched}


def _saved_dates(database_url: str, year: int) -> set[date]:
    with connect_postgres(database_url) as connection:
        rows = connection.execute(
            """
            SELECT holiday_date FROM public_holidays
            WHERE holiday_date >= %s AND holiday_date < %s
            """,
            (date(year, 1, 1), date(year + 1, 1, 1)),
        ).fetchall()
    return {row[0] for row in rows}


def _year_was_saved(database_url: str, year: int) -> bool:
    with connect_postgres(database_url) as connection:
        row = connection.execute(
            """
            SELECT 1 FROM holiday_fetch_logs
            WHERE calendar_year = %s AND status = 'accepted'
            LIMIT 1
            """,
            (year,),
        ).fetchone()
    return row is not None


def _replace_year(database_url: str, year: int, holidays: list[dict]) -> None:
    with connect_postgres(database_url) as connection:
        connection.execute(
            """
            DELETE FROM public_holidays
            WHERE holiday_date >= %s AND holiday_date < %s
            """,
            (date(year, 1, 1), date(year + 1, 1, 1)),
        )
        for item in holidays:
            connection.execute(
                """
                INSERT INTO public_holidays (holiday_date, local_name, name)
                VALUES (%s, %s, %s)
                """,
                (item["date"], item["local_name"], item["name"]),
            )
        connection.commit()


def _log(database_url: str, year: int, status: str, message: str) -> None:
    with connect_postgres(database_url) as connection:
        connection.execute(
            """
            INSERT INTO holiday_fetch_logs (calendar_year, status, message)
            VALUES (%s, %s, %s)
            """,
            (year, status, message),
        )
        connection.commit()
