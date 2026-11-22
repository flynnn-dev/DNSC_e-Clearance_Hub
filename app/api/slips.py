"""Issue a signed clearance slip and check one in public."""

from flask import Blueprint, current_app, jsonify, request

from app.auth.session import current_user, role_required
from app.db.users import connect
from app.security.csrf import csrf_matches
from app.services.slip_service import SlipError, issue_slip, qr_svg, verify_slip

bp = Blueprint("slips_api", __name__)


@bp.post("/api/me/slip")
@role_required("student")
def issue():
    if not csrf_matches(_provided_token()):
        return jsonify(error="The form expired. Refresh the page and try again."), 400
    user = current_user()
    try:
        with connect() as connection:
            issued = issue_slip(connection, user["id"], current_app.config["SLIP_SIGNING_KEY"])
            connection.commit()
    except SlipError as exc:
        return jsonify(error=str(exc)), exc.status
    verify_path = f"/verify/{issued['token']}"
    try:
        svg = qr_svg(request.host_url.rstrip("/") + verify_path)
    except SlipError as exc:
        return jsonify(error=str(exc)), exc.status
    return jsonify(verify_path=verify_path, expires_at=issued["expires_at"], qr_svg=svg)


@bp.get("/api/verify/<token>")
def verify(token: str):
    try:
        with connect() as connection:
            payload = verify_slip(connection, token, current_app.config["SLIP_SIGNING_KEY"])
    except SlipError as exc:
        return jsonify(verified=False, cleared=False, message=str(exc)), exc.status
    return jsonify(payload)


def _provided_token() -> str | None:
    header = request.headers.get("X-CSRF-Token")
    if header:
        return header
    payload = request.get_json(silent=True) if request.is_json else request.form
    token = payload.get("csrf_token") if payload else None
    return token if isinstance(token, str) else None
