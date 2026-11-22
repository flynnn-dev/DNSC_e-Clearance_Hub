"""Student and staff clearance routes."""

import re

from flask import Blueprint, current_app, jsonify, request

from app.auth.session import current_user, role_required
from app.db.users import connect
from app.security.csrf import csrf_matches
from app.services.deadline_service import clearance_deadline
from app.services.clearance_service import (
    ClearanceError,
    place_hold,
    sign_off,
    staff_queue,
    student_view,
)

bp = Blueprint("clearance_api", __name__)
_STUDENT_ID = re.compile(r"^\d{4}-\d{5}$")


@bp.get("/api/me/clearance")
@role_required("student")
def my_clearance():
    user = current_user()
    with connect() as connection:
        payload = student_view(connection, user["id"])
    payload.update(
        clearance_deadline(
            current_app.config["DATABASE_URL"],
            current_app.config.get("CLEARANCE_ANCHOR_DATE", ""),
            current_app.config.get("CLEARANCE_WORKING_DAYS", ""),
        )
    )
    return jsonify(payload)


@bp.get("/api/staff/clearance")
@role_required("staff")
def office_queue():
    user = current_user()
    with connect() as connection:
        try:
            payload = staff_queue(connection, user["office"])
        except ClearanceError as exc:
            return jsonify(error=str(exc)), exc.status
    return jsonify(payload)


@bp.post("/api/staff/clearance/<student_number>/hold")
@role_required("staff")
def hold_student(student_number: str):
    return _change(student_number, hold=True)


@bp.post("/api/staff/clearance/<student_number>/signoff")
@role_required("staff")
def sign_off_student(student_number: str):
    return _change(student_number, hold=False)


def _change(student_number: str, hold: bool):
    if not _STUDENT_ID.fullmatch(student_number):
        return jsonify(error="Student not found."), 404
    if not csrf_matches(_provided_token()):
        return jsonify(error="The form expired. Refresh the page and try again."), 400
    user = current_user()
    reason = ""
    if hold:
        payload = request.get_json(silent=True) if request.is_json else request.form
        reason = str(payload.get("reason", "")) if payload else ""
    try:
        with connect() as connection:
            result = place_hold(connection, user, student_number, reason) if hold else sign_off(connection, user, student_number)
            connection.commit()
    except ClearanceError as exc:
        return jsonify(error=str(exc)), exc.status
    return jsonify(result)


def _provided_token() -> str | None:
    header = request.headers.get("X-CSRF-Token")
    if header:
        return header
    payload = request.get_json(silent=True) if request.is_json else request.form
    token = payload.get("csrf_token") if payload else None
    return token if isinstance(token, str) else None
