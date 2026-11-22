"""Client for the instructor's mock Registrar API."""

import time
from urllib.parse import urljoin

import requests

_PAGE_SIZE = 20
_MAX_ATTEMPTS = 4


class RegistrarError(Exception):
    """The masterlist could not be read."""


class RegistrarClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0):
        if not base_url:
            raise RegistrarError("REGISTRAR_BASE_URL is empty.")
        if not api_key:
            raise RegistrarError("REGISTRAR_API_KEY is empty.")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = api_key
        self._session.headers["Accept"] = "application/json"

    def fetch_masterlist(self) -> list[dict]:
        page = 1
        students: list[dict] = []
        while True:
            body = self._get_json(
                "api/v1/students",
                params={"page": page, "size": _PAGE_SIZE},
            )
            rows = body.get("data")
            if not isinstance(rows, list):
                raise RegistrarError("Registrar returned a student list without a data array.")
            students.extend(rows)
            if not body.get("has_next") or not rows:
                return students
            page += 1
            if page > 1000:
                raise RegistrarError("Registrar pagination did not end.")

    def fetch_student(self, student_id: str) -> dict:
        body = self._get_json(f"api/v1/students/{student_id}")
        if not isinstance(body, dict):
            raise RegistrarError("Registrar returned a student record that is not an object.")
        return body

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        url = urljoin(self.base_url, path)
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._session.get(url, params=params, timeout=self.timeout)
            except requests.Timeout as exc:
                raise RegistrarError("Registrar request timed out.") from exc
            except requests.RequestException as exc:
                raise RegistrarError("Registrar request failed.") from exc
            if response.status_code == 503 and attempt < _MAX_ATTEMPTS:
                time.sleep(_retry_delay(response))
                continue
            if response.status_code == 401:
                raise RegistrarError("Registrar rejected the API key.")
            if response.status_code == 404:
                raise RegistrarError("Registrar could not find that record.")
            if response.status_code >= 400:
                raise RegistrarError(f"Registrar returned HTTP {response.status_code}.")
            try:
                body = response.json()
            except ValueError as exc:
                raise RegistrarError("Registrar returned invalid JSON.") from exc
            if not isinstance(body, dict):
                raise RegistrarError("Registrar returned JSON that is not an object.")
            return body
        raise RegistrarError("Registrar stayed unavailable.")


def _retry_delay(response: requests.Response) -> float:
    try:
        delay = float(response.headers.get("Retry-After", "1"))
    except ValueError:
        delay = 1.0
    return min(max(delay, 0.0), 5.0)
