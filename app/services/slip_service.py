"""Signed clearance slips.

A slip is issued only when the overall status is CLEARED. The token is an
HMAC-SHA256 signature over the student number, the expiry, and a random nonce.
The signing key stays on the server. The database stores the SHA-256 of the
token, not the token itself. The QR code contains the public verification URL.

The slip lasts 14 calendar days. That lifetime is separate from the working-day
count, which is still not attached to a clearance.
"""

import base64
import hashlib
import hmac
import io
import re
import secrets
from datetime import datetime, timedelta, timezone

import segno

from app.security.masking import mask_student_number

SLIP_LIFETIME = timedelta(days=14)
_STUDENT_NUMBER = re.compile(r"^\d{4}-\d{5}$")
_SIGNATURE = re.compile(r"^[0-9a-f]{64}$")


class SlipError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def issue_slip(connection, user_id: int, signing_key: str) -> dict:
    key = _key(signing_key, issuing=True)
    student = connection.execute(
        """
        SELECT students.id, students.student_number, clearance.overall_status
        FROM students
        LEFT JOIN clearance ON clearance.student_id = students.id
        WHERE students.user_id = %s
        """,
        (user_id,),
    ).fetchone()
    if student is None:
        raise SlipError("No Registrar student is linked to this account.", 404)
    student_id, student_number, overall = student
    if overall != "CLEARED":
        raise SlipError("A slip can be issued only when the overall status is cleared.", 409)
    expires = datetime.now(timezone.utc).replace(microsecond=0) + SLIP_LIFETIME
    payload = f"{student_number}|{expires.isoformat()}|{secrets.token_hex(16)}"
    signature = _sign(payload, key)
    token = _pack(payload, signature)
    connection.execute(
        """
        INSERT INTO clearance_tokens (student_id, token_hash, issued_at, expires_at)
        VALUES (%s, %s, now(), %s)
        """,
        (student_id, hashlib.sha256(token.encode("utf-8")).hexdigest(), expires),
    )
    connection.execute(
        """
        INSERT INTO clearance_events (student_id, office, action, reason, actor_user_id)
        VALUES (%s, NULL, 'slip_issued', 'Signed clearance slip issued.', %s)
        """,
        (student_id, user_id),
    )
    connection.execute(
        """
        INSERT INTO audit_logs (actor_user_id, action, student_id, office, detail)
        VALUES (%s, 'slip_issued', %s, NULL, 'Issued a signed clearance slip.')
        """,
        (user_id, student_id),
    )
    return {"token": token, "expires_at": expires.isoformat()}


def verify_slip(connection, token: str, signing_key: str) -> dict:
    key = _key(signing_key, issuing=False)
    unpacked = _unpack(token)
    if unpacked is None:
        raise SlipError("This slip could not be verified.", 404)
    payload, signature = unpacked
    if not hmac.compare_digest(_sign(payload, key), signature):
        raise SlipError("This slip could not be verified.", 404)
    parts = payload.split("|")
    if len(parts) != 3 or not _STUDENT_NUMBER.fullmatch(parts[0]):
        raise SlipError("This slip could not be verified.", 404)
    student_number = parts[0]
    row = connection.execute(
        """
        SELECT clearance_tokens.expires_at, clearance_tokens.revoked_at,
               students.student_number, clearance.overall_status
        FROM clearance_tokens
        JOIN students ON students.id = clearance_tokens.student_id
        LEFT JOIN clearance ON clearance.student_id = students.id
        WHERE clearance_tokens.token_hash = %s
        """,
        (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
    ).fetchone()
    if row is None or row[2] != student_number:
        raise SlipError("This slip could not be verified.", 404)
    expires_at, revoked_at, _stored_number, overall = row
    masked = mask_student_number(student_number)
    expires_text = expires_at.isoformat()
    if revoked_at is not None:
        return _public(False, "revoked", masked, expires_text, "This slip was revoked because the clearance changed.")
    if expires_at < datetime.now(timezone.utc):
        return _public(False, "expired", masked, expires_text, "This slip has expired.")
    if overall != "CLEARED":
        return _public(
            False,
            overall or "PENDING",
            masked,
            expires_text,
            "This slip is signed, and the student is not cleared.",
        )
    return _public(True, "CLEARED", masked, expires_text, "This slip is signed and the student is cleared.")


def revoke_open_slips(connection, student_id: int) -> None:
    rows = connection.execute(
        """
        UPDATE clearance_tokens
        SET revoked_at = now()
        WHERE student_id = %s AND revoked_at IS NULL
        RETURNING id
        """,
        (student_id,),
    ).fetchall()
    if not rows:
        return
    connection.execute(
        """
        INSERT INTO audit_logs (actor_user_id, action, student_id, office, detail)
        VALUES (NULL, 'slip_revoked', %s, NULL, 'Open clearance slips were revoked because the clearance is on hold.')
        """,
        (student_id,),
    )


def qr_svg(url: str) -> str:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="svg", xmldecl=False, svgns=True, nl=False, scale=4)
    svg = buffer.getvalue().decode("utf-8")
    if not svg.startswith("<svg"):
        raise SlipError("The slip QR code could not be created.", 500)
    return svg


def _public(cleared: bool, status: str, student_number: str, expires_at: str, message: str) -> dict:
    return {
        "verified": True,
        "cleared": cleared,
        "status": status,
        "student_number": student_number,
        "expires_at": expires_at,
        "message": message,
    }


def _key(signing_key: str, *, issuing: bool) -> bytes:
    if not isinstance(signing_key, str) or not signing_key.strip():
        if issuing:
            raise SlipError("A clearance slip cannot be issued right now.", 503)
        raise SlipError("This slip could not be verified.", 404)
    return signing_key.strip().encode("utf-8")


def _sign(payload: str, key: bytes) -> str:
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _pack(payload: str, signature: str) -> str:
    body = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{body}.{signature}"


def _unpack(token: str) -> tuple[str, str] | None:
    if not isinstance(token, str) or len(token) > 400 or token.count(".") != 1:
        return None
    body, signature = token.split(".", 1)
    if not body or not _SIGNATURE.fullmatch(signature):
        return None
    padding = "=" * (-len(body) % 4)
    try:
        payload = base64.urlsafe_b64decode(body + padding).decode("utf-8")
    except (ValueError, UnicodeError):
        return None
    return payload, signature
