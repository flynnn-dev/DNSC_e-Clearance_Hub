"""Read an Accounting balance export and store the unpaid rows."""

import csv
import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path

from psycopg.types.json import Json

from app.db.postgres_repo import connect_postgres
from app.importers.manifest import signature_problem
from app.services.slip_service import revoke_open_slips

_STUDENT_ID = re.compile(r"^\d{4}-\d{5}$")
_COLUMNS = ["StudentNo", "Name", "Term", "Assessed", "Paid", "Balance", "LastPaymentDate"]


class AccountingCsvError(Exception):
    """The Accounting file could not be read."""


def import_accounting_file(database_url: str, path: str | Path) -> dict:
    file_path = Path(path)
    try:
        payload = file_path.read_bytes()
    except OSError as exc:
        raise AccountingCsvError(f"Could not read {file_path.name}.") from exc
    digest = hashlib.sha256(payload).hexdigest()
    try:
        manifest = _load_manifest(file_path)
    except AccountingCsvError as exc:
        _log_failure(database_url, file_path.name, str(exc))
        raise
    if manifest is not None:
        problem = _manifest_before_rows(manifest, digest, file_path.name)
        if problem:
            _log_failure(database_url, file_path.name, problem)
            raise AccountingCsvError(problem)
    try:
        rows = parse_accounting_csv(payload.decode("utf-8"))
    except AccountingCsvError as exc:
        _log_failure(database_url, file_path.name, str(exc))
        raise
    if manifest is not None and manifest.get("record_count") != len(rows):
        problem = "Accounting manifest record_count does not match the CSV."
        _log_failure(database_url, file_path.name, problem)
        raise AccountingCsvError(problem)
    manifest_id = _nonce(manifest)
    if manifest_id and _nonce_was_accepted(database_url, manifest_id):
        message = "This Accounting manifest was already imported."
        _log_failure(database_url, file_path.name, message)
        raise AccountingCsvError(message)
    return _store(database_url, file_path.name, digest, rows, manifest_id)


def parse_accounting_csv(text: str) -> list[dict]:
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames != _COLUMNS:
        raise AccountingCsvError("Accounting CSV headers must be StudentNo,Name,Term,Assessed,Paid,Balance,LastPaymentDate.")
    rows = []
    for index, row in enumerate(reader, start=1):
        item = {column: (row.get(column) or "").strip() for column in _COLUMNS}
        item["row_number"] = index
        rows.append(item)
    return rows


def manifest_problem(manifest: dict, digest: str, filename: str, row_count: int) -> str | None:
    problem = _manifest_before_rows(manifest, digest, filename)
    if problem:
        return problem
    if manifest.get("record_count") != row_count:
        return "Accounting manifest record_count does not match the CSV."
    return None


def _manifest_before_rows(manifest: dict, digest: str, filename: str) -> str | None:
    signed = signature_problem(manifest)
    if signed:
        if signed.startswith("HMAC_SECRET"):
            return signed
        return "Accounting manifest signature is invalid."
    if manifest.get("sha256") != digest:
        return "Accounting manifest sha256 does not match the CSV."
    if manifest.get("file") != filename:
        return "Accounting manifest names a different file."
    if manifest.get("source") not in (None, "accounting"):
        return "Accounting manifest source must be accounting."
    return None


def classify_balances(rows: list[dict], known_student_numbers: set[str]) -> tuple[list[dict], list[dict]]:
    accepted = []
    rejected = []
    seen = set()
    for row in rows:
        record, reason = _validate(row)
        if reason:
            rejected.append(_rejection(row, reason))
            continue
        if record["student_number"] in seen:
            rejected.append(_rejection(row, "duplicate StudentNo in this file"))
            continue
        seen.add(record["student_number"])
        if record["student_number"] not in known_student_numbers:
            rejected.append(_rejection(row, "student is not in the Registrar masterlist"))
            continue
        accepted.append(record)
    return accepted, rejected


def _validate(row: dict) -> tuple[dict | None, str | None]:
    student_number = row.get("StudentNo", "")
    if not isinstance(student_number, str) or not _STUDENT_ID.fullmatch(student_number):
        return None, "StudentNo must look like 2023-59928"
    assessed = _cents(row.get("Assessed", ""))
    paid = _cents(row.get("Paid", ""))
    balance = _cents(row.get("Balance", ""))
    if assessed is None or paid is None or balance is None:
        return None, "Assessed, Paid, and Balance must be peso amounts"
    if assessed - paid != balance:
        return None, "Balance must equal Assessed minus Paid"
    paid_on = row.get("LastPaymentDate", "")
    if paid_on and not _real_date(paid_on):
        return None, "LastPaymentDate is not a real date"
    term = row.get("Term", "") or "Balance"
    return {
        "student_number": student_number,
        "balance_cents": balance,
        "blocking": balance > 0,
        "description": term,
        "title": _label(balance, term),
        "payload": {key: value for key, value in row.items() if key != "row_number"},
        "row_number": row.get("row_number"),
    }, None


def _cents(value: str) -> int | None:
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if amount < 0 or amount.as_tuple().exponent < -2:
        return None
    return int(amount * 100)


def _real_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _label(balance_cents: int, term: str) -> str:
    pesos = f"{Decimal(balance_cents) / Decimal(100):,.2f}"
    if term == "Balance":
        return f"Balance {pesos}"
    return f"Balance {pesos} for {term}"


def _rejection(row: dict, reason: str) -> dict:
    student_number = row.get("StudentNo")
    if not isinstance(student_number, str) or not student_number:
        student_number = None
    return {
        "student_number": student_number,
        "row_number": row.get("row_number"),
        "reason": reason,
        "raw": row,
    }


def _nonce(manifest: dict | None) -> str | None:
    if not isinstance(manifest, dict):
        return None
    nonce = manifest.get("nonce")
    if isinstance(nonce, str) and nonce.strip():
        return nonce.strip()
    return None


def _nonce_was_accepted(database_url: str, manifest_id: str) -> bool:
    with connect_postgres(database_url) as connection:
        row = connection.execute(
            """
            SELECT 1 FROM import_logs
            WHERE status = 'accepted' AND manifest_id = %s
            """,
            (manifest_id,),
        ).fetchone()
    return row is not None


def _load_manifest(path: Path) -> dict | None:
    manifest_path = Path(str(path) + ".manifest.json")
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AccountingCsvError("Accounting manifest could not be read.") from exc
    if not isinstance(data, dict):
        raise AccountingCsvError("Accounting manifest could not be read.")
    return data


def _store(database_url: str, filename: str, digest: str, rows: list[dict], manifest_id: str | None = None) -> dict:
    with connect_postgres(database_url) as connection:
        known = {number for (number,) in connection.execute("SELECT student_number FROM students")}
        accepted, rejected = classify_balances(rows, known)
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
            "Accounting export imported.",
            manifest_id,
        )
        if numbers:
            connection.execute(
                "DELETE FROM accounting_records WHERE student_id = ANY(%s)",
                (list(ids.values()),),
            )
        for record in accepted:
            student_id = ids[record["student_number"]]
            if record["blocking"]:
                connection.execute(
                    """
                    INSERT INTO accounting_records (
                        student_id, import_log_id, description, balance_cents, is_blocking, source_payload
                    )
                    VALUES (%s, %s, %s, %s, TRUE, %s)
                    """,
                    (student_id, log_id, record["description"], record["balance_cents"], Json(record["payload"])),
                )
            _apply_accounting_status(connection, student_id, record)
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


def _apply_accounting_status(connection, student_id: int, record: dict) -> None:
    connection.execute(
        """
        INSERT INTO office_clearance (student_id, office, status)
        VALUES (%s, 'accounting', 'PENDING')
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
        WHERE student_id = %s AND office = 'accounting'
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
            "SELECT hold_reason FROM office_clearance WHERE student_id = %s AND office = 'accounting'",
            (student_id,),
        ).fetchone()[0]
        event = "import"
        event_reason = "Accounting import has no balance. The staff hold remains."
    elif signed_off_by is not None and signed_off_at is not None:
        status = "CLEARED"
        hold_reason = None
        event = "import"
        event_reason = "Accounting import has no balance."
    else:
        status = "PENDING"
        hold_reason = None
        signed_off_by = None
        signed_off_at = None
        event = "import"
        event_reason = "Accounting import has no balance."
    connection.execute(
        """
        UPDATE office_clearance
        SET status = %s,
            hold_reason = %s,
            signed_off_by = %s,
            signed_off_at = %s,
            updated_at = now()
        WHERE student_id = %s AND office = 'accounting'
        """,
        (status, hold_reason, signed_off_by, signed_off_at, student_id),
    )
    connection.execute(
        """
        INSERT INTO clearance_events (student_id, office, action, reason)
        VALUES (%s, 'accounting', %s, %s)
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
        WHERE student_id = %s AND office = 'accounting' AND action IN ('hold', 'signoff')
        ORDER BY id DESC
        LIMIT 1
        """,
        (student_id,),
    ).fetchone()
    return row is not None and row[0] == "hold" and row[1] is not None


def _import_log(
    connection,
    status: str,
    filename: str,
    digest: str,
    accepted: int,
    rejected: int,
    message: str,
    manifest_id: str | None = None,
) -> int:
    row = connection.execute(
        """
        INSERT INTO import_logs (
            source, filename, file_sha256, manifest_id, status, rows_accepted, rows_rejected, message
        )
        VALUES ('accounting_csv', %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (filename, digest or None, manifest_id, status, accepted, rejected, message),
    ).fetchone()
    return row[0]


def _log_failure(database_url: str, filename: str, message: str) -> None:
    with connect_postgres(database_url) as connection:
        _import_log(connection, "rejected", filename, "", 0, 0, message)
        connection.commit()
