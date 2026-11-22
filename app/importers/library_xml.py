"""Read a Library borrower export and store the current rows."""

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

from psycopg.types.json import Json

from app.db.postgres_repo import connect_postgres
from app.importers.manifest import signature_problem
from app.services.slip_service import revoke_open_slips

_STUDENT_ID = re.compile(r"^\d{4}-\d{5}$")


class LibraryXmlError(Exception):
    """The Library file could not be read."""


def import_library_file(database_url: str, path: str | Path) -> dict:
    file_path = Path(path)
    try:
        payload = file_path.read_bytes()
    except OSError as exc:
        raise LibraryXmlError(f"Could not read {file_path.name}.") from exc
    digest = hashlib.sha256(payload).hexdigest()
    try:
        manifest = _load_manifest(file_path)
        if manifest is not None:
            problem = _manifest_before_rows(manifest, digest, file_path.name)
            if problem:
                raise LibraryXmlError(problem)
        rows = parse_library_xml(payload.decode("utf-8"))
    except LibraryXmlError as exc:
        _log_failure(database_url, file_path.name, str(exc))
        raise
    return _store(database_url, file_path.name, digest, rows)


def _load_manifest(path: Path) -> dict | None:
    manifest_path = Path(str(path) + ".manifest.json")
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryXmlError("Library manifest could not be read.") from exc
    if not isinstance(data, dict):
        raise LibraryXmlError("Library manifest could not be read.")
    return data


def _manifest_before_rows(manifest: dict, digest: str, filename: str) -> str | None:
    signed = signature_problem(manifest)
    if signed:
        if signed.startswith("HMAC_SECRET"):
            return signed
        return "Library manifest signature is invalid."
    if manifest.get("sha256") != digest:
        return "Library manifest sha256 does not match the XML."
    if manifest.get("file") not in (None, filename):
        return "Library manifest names a different file."
    if manifest.get("source") not in (None, "library"):
        return "Library manifest source must be library."
    return None


def parse_library_xml(text: str) -> list[dict]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise LibraryXmlError("Library XML could not be parsed.") from exc
    if root.tag != "borrowers":
        raise LibraryXmlError("Library XML root must be borrowers.")
    rows = []
    for index, node in enumerate(root.findall("borrower"), start=1):
        fields = {child.tag: (child.text or "").strip() for child in list(node)}
        fields["card"] = (node.attrib.get("card") or "").strip()
        fields["row_number"] = index
        rows.append(fields)
    return rows


def classify_borrowers(rows: list[dict], known_student_numbers: set[str]) -> tuple[list[dict], list[dict]]:
    accepted = []
    rejected = []
    seen = set()
    for row in rows:
        record, reason = _validate(row)
        if reason:
            rejected.append(_rejection(row, reason))
            continue
        if record["student_number"] in seen:
            rejected.append(_rejection(row, "duplicate studentNo in this file"))
            continue
        seen.add(record["student_number"])
        if record["student_number"] not in known_student_numbers:
            rejected.append(_rejection(row, "student is not in the Registrar masterlist"))
            continue
        accepted.append(record)
    return accepted, rejected


def _validate(row: dict) -> tuple[dict | None, str | None]:
    student_number = row.get("studentNo", "")
    if not isinstance(student_number, str) or not _STUDENT_ID.fullmatch(student_number):
        return None, "studentNo must look like 2023-59928"
    try:
        unreturned = int(row.get("unreturnedBooks", ""))
    except (TypeError, ValueError):
        return None, "unreturnedBooks must be a whole number"
    if unreturned < 0:
        return None, "unreturnedBooks must be zero or more"
    try:
        fine = Decimal(row.get("unpaidFines", ""))
    except (InvalidOperation, TypeError):
        return None, "unpaidFines must be a peso amount"
    if fine < 0 or fine.as_tuple().exponent < -2:
        return None, "unpaidFines must be zero or more, with at most two decimal places"
    borrowed = row.get("lastBorrowed", "")
    if borrowed and not _real_date(borrowed):
        return None, "lastBorrowed is not a real date"
    fine_cents = int(fine * 100)
    blocking = unreturned > 0 or fine_cents > 0
    return {
        "student_number": student_number,
        "unreturned": unreturned,
        "fine_cents": fine_cents,
        "blocking": blocking,
        "title": _label(unreturned, fine_cents),
        "payload": {key: value for key, value in row.items() if key != "row_number"},
        "row_number": row.get("row_number"),
    }, None


def _real_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return False
    return True


def _label(unreturned: int, fine_cents: int) -> str:
    parts = []
    if unreturned == 1:
        parts.append("1 unreturned book")
    elif unreturned > 1:
        parts.append(f"{unreturned} unreturned books")
    if fine_cents > 0:
        parts.append(f"unpaid fine {Decimal(fine_cents) / Decimal(100):.2f}")
    return "; ".join(parts)


def _rejection(row: dict, reason: str) -> dict:
    student_number = row.get("studentNo")
    if not isinstance(student_number, str) or not student_number:
        student_number = None
    return {
        "student_number": student_number,
        "row_number": row.get("row_number"),
        "reason": reason,
        "raw": row,
    }


def _store(database_url: str, filename: str, digest: str, rows: list[dict]) -> dict:
    with connect_postgres(database_url) as connection:
        known = {
            number
            for (number,) in connection.execute("SELECT student_number FROM students")
        }
        accepted, rejected = classify_borrowers(rows, known)
        numbers = [record["student_number"] for record in accepted]
        ids = {}
        if numbers:
            ids = dict(connection.execute(
                "SELECT student_number, id FROM students WHERE student_number = ANY(%s)",
                (numbers,),
            ).fetchall())
        log_id = _import_log(
            connection,
            "accepted",
            filename,
            digest,
            len(accepted),
            len(rejected),
            "Library export imported.",
        )
        if numbers:
            connection.execute(
                "DELETE FROM library_records WHERE student_id = ANY(%s)",
                (list(ids.values()),),
            )
        for record in accepted:
            student_id = ids[record["student_number"]]
            connection.execute(
                """
                INSERT INTO library_records (
                    student_id, import_log_id, title, is_unreturned, fine_cents, is_blocking, source_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    student_id,
                    log_id,
                    record["title"],
                    record["unreturned"] > 0,
                    record["fine_cents"],
                    record["blocking"],
                    Json(record["payload"]),
                ),
            )
            _apply_library_status(connection, student_id, record)
        for item in rejected:
            connection.execute(
                """
                INSERT INTO rejected_records (import_log_id, student_number, row_number, reason, raw_row)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    log_id,
                    item["student_number"],
                    item["row_number"],
                    item["reason"],
                    json.dumps(item["raw"], ensure_ascii=False),
                ),
            )
        connection.commit()
    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "blocking": sum(1 for record in accepted if record["blocking"]),
    }


def _apply_library_status(connection, student_id: int, record: dict) -> None:
    connection.execute(
        """
        INSERT INTO office_clearance (student_id, office, status)
        VALUES (%s, 'library', 'PENDING')
        ON CONFLICT (student_id, office) DO NOTHING
        """,
        (student_id,),
    )
    connection.execute(
        """
        INSERT INTO clearance (student_id, overall_status)
        VALUES (%s, 'PENDING')
        ON CONFLICT (student_id) DO NOTHING
        """,
        (student_id,),
    )
    current = connection.execute(
        """
        SELECT signed_off_by, signed_off_at
        FROM office_clearance
        WHERE student_id = %s AND office = 'library'
        """,
        (student_id,),
    ).fetchone()
    signed_off_by, signed_off_at = current
    if record["blocking"]:
        status = "HOLD"
        hold_reason = record["title"]
        signed_off_by = None
        signed_off_at = None
        event = "hold"
        event_reason = record["title"]
    elif _staff_hold_stands(connection, student_id):
        status = "HOLD"
        hold_reason = connection.execute(
            "SELECT hold_reason FROM office_clearance WHERE student_id = %s AND office = 'library'",
            (student_id,),
        ).fetchone()[0]
        event = "import"
        event_reason = "Library import has no blocking condition. The staff hold remains."
    elif signed_off_by is not None and signed_off_at is not None:
        status = "CLEARED"
        hold_reason = None
        event = "import"
        event_reason = "Library import has no blocking condition."
    else:
        status = "PENDING"
        hold_reason = None
        signed_off_by = None
        signed_off_at = None
        event = "import"
        event_reason = "Library import has no blocking condition."
    connection.execute(
        """
        UPDATE office_clearance
        SET status = %s,
            hold_reason = %s,
            signed_off_by = %s,
            signed_off_at = %s,
            updated_at = now()
        WHERE student_id = %s AND office = 'library'
        """,
        (status, hold_reason, signed_off_by, signed_off_at, student_id),
    )
    connection.execute(
        """
        INSERT INTO clearance_events (student_id, office, action, reason)
        VALUES (%s, 'library', %s, %s)
        """,
        (student_id, event, event_reason),
    )
    if status == "HOLD" and record["blocking"]:
        revoke_open_slips(connection, student_id)
    offices = [
        row[0]
        for row in connection.execute(
            "SELECT status FROM office_clearance WHERE student_id = %s",
            (student_id,),
        )
    ]
    if "HOLD" in offices:
        overall = "HOLD"
    elif len(offices) >= 2 and all(item == "CLEARED" for item in offices):
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


def _staff_hold_stands(connection, student_id: int) -> bool:
    row = connection.execute(
        """
        SELECT action, actor_user_id
        FROM clearance_events
        WHERE student_id = %s AND office = 'library' AND action IN ('hold', 'signoff')
        ORDER BY id DESC
        LIMIT 1
        """,
        (student_id,),
    ).fetchone()
    return row is not None and row[0] == "hold" and row[1] is not None


def _import_log(connection, status: str, filename: str, digest: str, accepted: int, rejected: int, message: str) -> int:
    row = connection.execute(
        """
        INSERT INTO import_logs (source, filename, file_sha256, status, rows_accepted, rows_rejected, message)
        VALUES ('library_xml', %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (filename, digest, status, accepted, rejected, message),
    ).fetchone()
    return row[0]


def _log_failure(database_url: str, filename: str, message: str) -> None:
    with connect_postgres(database_url) as connection:
        _import_log(connection, "rejected", filename, "", 0, 0, message)
        connection.commit()
