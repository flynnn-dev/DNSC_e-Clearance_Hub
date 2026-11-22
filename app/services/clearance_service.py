"""Read clearance and apply a staff hold or sign-off."""

from psycopg.rows import dict_row

from app.services.slip_service import revoke_open_slips

_OFFICES = ("library", "accounting")


class ClearanceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def student_view(connection, user_id: int) -> dict:
    with connection.cursor(row_factory=dict_row) as cursor:
        student = cursor.execute(
            """
            SELECT students.id, students.student_number, students.display_name,
                   students.registrar_payload, clearance.overall_status
            FROM students
            LEFT JOIN clearance ON clearance.student_id = students.id
            WHERE students.user_id = %s
            """,
            (user_id,),
        ).fetchone()
        if student is None:
            return {"linked": False}
        offices = cursor.execute(
            """
            SELECT office, status, hold_reason
            FROM office_clearance
            WHERE student_id = %s
            ORDER BY office
            """,
            (student["id"],),
        ).fetchall()
        library = cursor.execute(
            """
            SELECT title FROM library_records
            WHERE student_id = %s
            ORDER BY id
            """,
            (student["id"],),
        ).fetchall()
        accounting = cursor.execute(
            """
            SELECT description, balance_cents FROM accounting_records
            WHERE student_id = %s
            ORDER BY id
            """,
            (student["id"],),
        ).fetchall()
        history = cursor.execute(
            """
            SELECT office, action, reason, created_at
            FROM clearance_events
            WHERE student_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 50
            """,
            (student["id"],),
        ).fetchall()
    payload = student["registrar_payload"] if isinstance(student["registrar_payload"], dict) else {}
    return {
        "linked": True,
        "student_number": student["student_number"],
        "display_name": student["display_name"],
        "program": _text(payload.get("program_name") or payload.get("program")),
        "year_level": payload.get("year_level"),
        "registrar_email": _text(payload.get("email")),
        "overall_status": student["overall_status"] or "PENDING",
        "offices": [
            {
                "office": row["office"],
                "status": row["status"],
                "reason": row["hold_reason"],
            }
            for row in offices
        ],
        "library_records": [row["title"] for row in library if row["title"]],
        "accounting_records": [
            f"{row['description']}: {_pesos(row['balance_cents'])}" for row in accounting
        ],
        "history": [
            {
                "at": row["created_at"].isoformat(),
                "office": row["office"],
                "action": row["action"],
                "reason": row["reason"],
            }
            for row in history
        ],
    }


def staff_queue(connection, office: str) -> dict:
    _office(office)
    blocking_sql = (
        "EXISTS (SELECT 1 FROM library_records WHERE student_id = students.id AND is_blocking)"
        if office == "library"
        else "EXISTS (SELECT 1 FROM accounting_records WHERE student_id = students.id)"
    )
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            f"""
            SELECT students.student_number, students.display_name,
                   office_clearance.status, office_clearance.hold_reason,
                   {blocking_sql} AS blocking
            FROM students
            JOIN office_clearance
              ON office_clearance.student_id = students.id
             AND office_clearance.office = %s
            ORDER BY students.student_number
            """,
            (office,),
        ).fetchall()
    counts = {"HOLD": 0, "PENDING": 0, "CLEARED": 0}
    students = []
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        students.append(
            {
                "student_number": row["student_number"],
                "display_name": row["display_name"],
                "status": row["status"],
                "reason": row["hold_reason"],
                "blocking": bool(row["blocking"]),
            }
        )
    return {"office": office, "counts": counts, "students": students}


def place_hold(connection, actor: dict, student_number: str, reason: str) -> dict:
    office = _actor_office(actor)
    text = reason.strip()
    if not text or len(text) > 500:
        raise ClearanceError("A hold needs a reason of 1 to 500 characters.")
    student_id = _student_id(connection, student_number)
    _ensure_rows(connection, student_id)
    connection.execute(
        """
        UPDATE office_clearance
        SET status = 'HOLD',
            hold_reason = %s,
            signed_off_by = NULL,
            signed_off_at = NULL,
            updated_at = now()
        WHERE student_id = %s AND office = %s
        """,
        (text, student_id, office),
    )
    _event(connection, student_id, office, "hold", text, actor["id"])
    _audit(connection, actor["id"], "hold", student_id, office, text)
    _revoke_tokens(connection, student_id)
    _refresh_overall(connection, student_id)
    return {"student_number": student_number, "office": office, "status": "HOLD"}


def sign_off(connection, actor: dict, student_number: str) -> dict:
    office = _actor_office(actor)
    student_id = _student_id(connection, student_number)
    if _blocking(connection, student_id, office):
        raise ClearanceError(
            "This office still has a blocking record, so it cannot be signed off.",
            409,
        )
    _ensure_rows(connection, student_id)
    connection.execute(
        """
        UPDATE office_clearance
        SET status = 'CLEARED',
            hold_reason = NULL,
            signed_off_by = %s,
            signed_off_at = now(),
            updated_at = now()
        WHERE student_id = %s AND office = %s
        """,
        (actor["id"], student_id, office),
    )
    _event(connection, student_id, office, "signoff", "Signed off.", actor["id"])
    _audit(connection, actor["id"], "signoff", student_id, office, "Signed off.")
    _refresh_overall(connection, student_id)
    return {"student_number": student_number, "office": office, "status": "CLEARED"}


def _actor_office(actor: dict) -> str:
    office = actor.get("office")
    if actor.get("role") != "staff" or office not in _OFFICES:
        raise ClearanceError("Only staff can change clearance.", 403)
    return office


def _office(office: str) -> None:
    if office not in _OFFICES:
        raise ClearanceError("The office is not available.", 403)


def _student_id(connection, student_number: str) -> int:
    row = connection.execute(
        "SELECT id FROM students WHERE student_number = %s",
        (student_number,),
    ).fetchone()
    if row is None:
        raise ClearanceError("Student not found.", 404)
    return row[0]


def _blocking(connection, student_id: int, office: str) -> bool:
    if office == "library":
        row = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM library_records
                WHERE student_id = %s AND is_blocking
            )
            """,
            (student_id,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM accounting_records WHERE student_id = %s)",
            (student_id,),
        ).fetchone()
    return bool(row[0])


def _ensure_rows(connection, student_id: int) -> None:
    for office in _OFFICES:
        connection.execute(
            """
            INSERT INTO office_clearance (student_id, office, status)
            VALUES (%s, %s, 'PENDING')
            ON CONFLICT (student_id, office) DO NOTHING
            """,
            (student_id, office),
        )
    connection.execute(
        """
        INSERT INTO clearance (student_id, overall_status)
        VALUES (%s, 'PENDING')
        ON CONFLICT (student_id) DO NOTHING
        """,
        (student_id,),
    )


def _event(connection, student_id: int, office: str, action: str, reason: str, actor_id: int) -> None:
    connection.execute(
        """
        INSERT INTO clearance_events (student_id, office, action, reason, actor_user_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (student_id, office, action, reason, actor_id),
    )


def _audit(connection, actor_id: int, action: str, student_id: int, office: str, detail: str) -> None:
    connection.execute(
        """
        INSERT INTO audit_logs (actor_user_id, action, student_id, office, detail)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (actor_id, action, student_id, office, detail),
    )


def _revoke_tokens(connection, student_id: int) -> None:
    revoke_open_slips(connection, student_id)


def _refresh_overall(connection, student_id: int) -> None:
    offices = [
        row[0]
        for row in connection.execute(
            "SELECT status FROM office_clearance WHERE student_id = %s",
            (student_id,),
        )
    ]
    if "HOLD" in offices:
        overall = "HOLD"
    elif len(offices) >= 2 and all(status == "CLEARED" for status in offices):
        overall = "CLEARED"
    else:
        overall = "PENDING"
    connection.execute(
        """
        UPDATE clearance
        SET overall_status = %s, updated_at = now()
        WHERE student_id = %s
        """,
        (overall, student_id),
    )


def _text(value) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _pesos(cents: int) -> str:
    from decimal import Decimal

    return f"{Decimal(cents) / Decimal(100):,.2f}"
