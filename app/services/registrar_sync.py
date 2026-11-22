"""Validate Registrar students and store them."""

import json
import re

from psycopg.types.json import Json

from app.db.postgres_repo import connect_postgres
from app.integrations.registrar_client import RegistrarClient, RegistrarError

_STUDENT_ID = re.compile(r"^\d{4}-\d{5}$")
_NAME_FIELDS = ("full_name", "name", "student_name", "display_name")


def sync_masterlist(database_url: str, base_url: str, api_key: str) -> dict:
    client = RegistrarClient(base_url, api_key)
    try:
        records = client.fetch_masterlist()
    except RegistrarError as exc:
        _log_failure(database_url, str(exc))
        raise
    accepted, rejected = _split(records)
    with connect_postgres(database_url) as connection:
        log_id = _import_log(connection, "accepted", len(accepted), len(rejected), "Masterlist synced.")
        for student in accepted:
            student_id = _upsert_student(connection, student)
            _ensure_clearance(connection, student_id)
        for reason, raw in rejected:
            _reject(connection, log_id, reason, raw)
        connection.commit()
    return {"accepted": len(accepted), "rejected": len(rejected)}


def _split(records: list[dict]) -> tuple[list[dict], list[tuple[str, dict]]]:
    accepted = []
    rejected = []
    seen = set()
    for record in records:
        student, reason = _normalize(record)
        if reason:
            rejected.append((reason, record))
            continue
        if student["student_number"] in seen:
            rejected.append(("duplicate student_id in this sync", record))
            continue
        seen.add(student["student_number"])
        accepted.append(student)
    return accepted, rejected


def _normalize(record: dict) -> tuple[dict | None, str | None]:
    if not isinstance(record, dict):
        return None, "record must be an object"
    student_id = record.get("student_id")
    if not isinstance(student_id, str) or not _STUDENT_ID.fullmatch(student_id):
        return None, "student_id must look like 2023-59928"
    display_name = _display_name(record, student_id)
    return {
        "student_number": student_id,
        "display_name": display_name,
        "payload": record,
    }, None


def _display_name(record: dict, student_id: str) -> str:
    for field in _NAME_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    parts = [
        record.get(field).strip()
        for field in ("first_name", "middle_initial", "last_name")
        if isinstance(record.get(field), str) and record.get(field).strip()
    ]
    return " ".join(parts) if parts else student_id


def _upsert_student(connection, student: dict) -> int:
    row = connection.execute(
        """
        INSERT INTO students (student_number, display_name, registrar_payload, last_synced_at)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (student_number) DO UPDATE
        SET display_name = EXCLUDED.display_name,
            registrar_payload = EXCLUDED.registrar_payload,
            last_synced_at = now()
        RETURNING id
        """,
        (student["student_number"], student["display_name"], Json(student["payload"])),
    ).fetchone()
    return row[0]


def _ensure_clearance(connection, student_id: int) -> None:
    for office in ("library", "accounting"):
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


def _import_log(connection, status: str, accepted: int, rejected: int, message: str) -> int:
    row = connection.execute(
        """
        INSERT INTO import_logs (source, status, rows_accepted, rows_rejected, message)
        VALUES ('registrar_api', %s, %s, %s, %s)
        RETURNING id
        """,
        (status, accepted, rejected, message),
    ).fetchone()
    return row[0]


def _reject(connection, log_id: int, reason: str, raw) -> None:
    student_number = raw.get("student_id") if isinstance(raw, dict) else None
    if not isinstance(student_number, str):
        student_number = None
    connection.execute(
        """
        INSERT INTO rejected_records (import_log_id, student_number, reason, raw_row)
        VALUES (%s, %s, %s, %s)
        """,
        (log_id, student_number, reason, json.dumps(raw, ensure_ascii=False)),
    )


def _log_failure(database_url: str, message: str) -> None:
    with connect_postgres(database_url) as connection:
        _import_log(connection, "rejected", 0, 0, message)
        connection.commit()
