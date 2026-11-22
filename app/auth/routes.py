"""Login, logout, and the current account."""

import re

from flask import Blueprint, jsonify, redirect, request, session, url_for

from app.auth.session import current_user, login_required
from app.db.users import connect, find_user_by_email
from app.security.csrf import csrf_matches, rotate_csrf_token
from app.security.passwords import verify_password

bp = Blueprint("auth", __name__)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FAILURE = "The email or password is incorrect."


@bp.post("/api/auth/login")
def login():
    if not csrf_matches(_provided_token()):
        return jsonify(error="The form expired. Refresh the page and try again."), 400
    email, password = _credentials()
    if email is None or password is None:
        return _reject()
    with connect() as connection:
        user = find_user_by_email(connection, email)
    if user is None or not verify_password(password, user["password_hash"]):
        return _reject()
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    rotate_csrf_token()
    if _wants_json():
        return jsonify(role=user["role"], email=user["email"])
    return redirect(_home_for(user["role"]))


@bp.post("/api/auth/logout")
@login_required
def logout():
    if not csrf_matches(_provided_token()):
        return jsonify(error="The form expired. Refresh the page and try again."), 400
    session.clear()
    if _wants_json():
        return jsonify(status="signed-out")
    return redirect(url_for("ui.login_page"))


@bp.get("/api/auth/me")
def me():
    user = current_user()
    if user is None:
        return jsonify(error="Sign in required."), 401
    return jsonify(email=user["email"], role=user["role"], office=user["office"])


def _credentials() -> tuple[str | None, str | None]:
    payload = request.get_json(silent=True) if request.is_json else request.form
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not _EMAIL.fullmatch(email) or len(email) > 254:
        return None, None
    if not password or len(password) > 200:
        return None, None
    return email, password


def _provided_token() -> str | None:
    header = request.headers.get("X-CSRF-Token")
    if header:
        return header
    payload = request.get_json(silent=True) if request.is_json else request.form
    token = payload.get("csrf_token")
    return token if isinstance(token, str) else None


def _wants_json() -> bool:
    return request.is_json or request.accept_mimetypes.best == "application/json"


def _reject():
    if _wants_json():
        return jsonify(error=_FAILURE), 401
    from flask import render_template

    return render_template("auth/login.html", notice=_FAILURE), 401


def _home_for(role: str) -> str:
    if role == "staff":
        return url_for("ui.staff_dashboard")
    return url_for("ui.student_dashboard")
