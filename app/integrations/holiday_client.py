"""Philippine public holidays from Nager.Date."""

from datetime import date

import requests


class HolidayError(Exception):
    """The holiday list could not be read."""


class HolidayClient:
    def __init__(self, timeout: float = 5.0, base_url: str = "https://date.nager.at/api/v3/PublicHolidays"):
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")

    def fetch_year(self, year: int) -> list[dict]:
        if year < 2000:
            raise HolidayError("The holiday year is not valid.")
        try:
            response = requests.get(
                f"{self.base_url}/{year}/PH",
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        except requests.Timeout as exc:
            raise HolidayError("The holiday request timed out.") from exc
        except requests.RequestException as exc:
            raise HolidayError("The holiday request failed.") from exc
        if response.status_code >= 400:
            raise HolidayError(f"Nager.Date returned HTTP {response.status_code}.")
        try:
            body = response.json()
        except ValueError as exc:
            raise HolidayError("Nager.Date returned invalid JSON.") from exc
        if not isinstance(body, list):
            raise HolidayError("Nager.Date did not return a holiday list.")
        holidays = []
        for item in body:
            parsed = _holiday(item)
            if parsed is not None:
                holidays.append(parsed)
        return holidays


def _holiday(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    types = item.get("types")
    if isinstance(types, list) and types and "Public" not in types:
        return None
    raw_date = item.get("date")
    try:
        holiday_date = date.fromisoformat(str(raw_date))
    except ValueError:
        return None
    local_name = item.get("localName")
    name = item.get("name")
    if not isinstance(local_name, str) or not local_name.strip():
        local_name = name if isinstance(name, str) else ""
    if not isinstance(name, str) or not name.strip():
        name = local_name
    if not local_name.strip() or not name.strip():
        return None
    return {"date": holiday_date, "local_name": local_name.strip(), "name": name.strip()}
