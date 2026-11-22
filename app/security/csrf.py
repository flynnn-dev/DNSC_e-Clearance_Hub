"""Session CSRF token for state-changing requests."""

import hmac
import secrets

from flask import session


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def rotate_csrf_token() -> None:
    session["csrf_token"] = secrets.token_urlsafe(32)


def csrf_matches(provided: str | None) -> bool:
    expected = session.get("csrf_token")
    if not isinstance(provided, str) or not isinstance(expected, str):
        return False
    if len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)
