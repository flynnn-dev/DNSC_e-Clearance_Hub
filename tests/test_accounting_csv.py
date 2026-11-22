"""Accounting CSV rows follow the starter export."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR

load_dotenv(BASE_DIR / ".env")

from app.importers.accounting_csv import (
    classify_balances,
    import_accounting_file,
    manifest_problem,
    parse_accounting_csv,
)

_SAMPLE = BASE_DIR / "samples" / "accounting" / "accounting_balances_2026-11-20.csv"
_MANIFEST = BASE_DIR / "samples" / "accounting" / "accounting_balances_2026-11-20.csv.manifest.json"
_REGISTRAR = BASE_DIR / "registrar_mock" / "registrar_students.json"


def test_sample_export_keeps_known_balances_and_rejects_planted_rows():
    known = {student["student_id"] for student in json.loads(_REGISTRAR.read_text(encoding="utf-8"))["students"]}
    text = _SAMPLE.read_text(encoding="utf-8")
    rows = parse_accounting_csv(text)
    accepted, rejected = classify_balances(rows, known)
    reasons = {item["student_number"]: item["reason"] for item in rejected}
    digest = hashlib.sha256(_SAMPLE.read_bytes()).hexdigest()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert len(rows) == 42
    assert len(accepted) == 40
    assert sum(1 for record in accepted if record["blocking"]) == 21
    assert reasons["2023-55555"] == "student is not in the Registrar masterlist"
    assert reasons["2024-45481"] == "Assessed, Paid, and Balance must be peso amounts"
    assert manifest_problem(manifest, digest, _SAMPLE.name, len(rows)) is None
    owed = next(record for record in accepted if record["student_number"] == "2024-46072")
    assert owed["balance_cents"] == 150_000
    assert owed["description"] == "1S 2026-2027"
    clean = next(record for record in accepted if record["student_number"] == "2026-29417")
    assert clean["blocking"] is False


def test_manifest_sha256_must_match_the_csv_bytes():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    problem = manifest_problem(manifest, "0" * 64, _SAMPLE.name, 42)
    assert problem == "Accounting manifest sha256 does not match the CSV."


def test_import_clears_an_accounting_hold_when_the_balance_is_paid():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    from app.db.postgres_repo import connect_postgres

    number = "2099-00019"
    folder = Path(os.environ["TEMP"]) / "dnsc-accounting-test"
    folder.mkdir(exist_ok=True)
    owed = folder / "owed.csv"
    paid = folder / "paid.csv"
    owed.write_text(_csv(number, "9200.00", "7700.00", "1500.00"), encoding="utf-8")
    paid.write_text(_csv(number, "9200.00", "9200.00", "0.00"), encoding="utf-8")
    with connect_postgres(database_url) as connection:
        connection.execute(
            """
            INSERT INTO students (student_number, display_name)
            VALUES (%s, 'Accounting Test')
            ON CONFLICT (student_number) DO NOTHING
            """,
            (number,),
        )
        connection.commit()
    try:
        assert import_accounting_file(database_url, owed)["blocking"] == 1
        with connect_postgres(database_url) as connection:
            connection.execute(
                """
                INSERT INTO office_clearance (student_id, office, status, hold_reason)
                SELECT id, 'library', 'HOLD', '1 unreturned book'
                FROM students WHERE student_number = %s
                ON CONFLICT (student_id, office) DO UPDATE
                SET status = 'HOLD', hold_reason = '1 unreturned book', signed_off_by = NULL, signed_off_at = NULL
                """,
                (number,),
            )
            connection.commit()
        result = import_accounting_file(database_url, paid)
        assert result["blocking"] == 0
        with connect_postgres(database_url) as connection:
            status = connection.execute(
                """
                SELECT
                    accounting.status,
                    library.status,
                    clearance.overall_status,
                    (SELECT COUNT(*) FROM accounting_records WHERE student_id = students.id)
                FROM students
                JOIN office_clearance AS accounting
                    ON accounting.student_id = students.id AND accounting.office = 'accounting'
                JOIN office_clearance AS library
                    ON library.student_id = students.id AND library.office = 'library'
                JOIN clearance ON clearance.student_id = students.id
                WHERE students.student_number = %s
                """,
                (number,),
            ).fetchone()
            assert status == ("PENDING", "HOLD", "HOLD", 0)
    finally:
        with connect_postgres(database_url) as connection:
            connection.execute(
                "DELETE FROM accounting_records WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
                (number,),
            )
            connection.execute(
                "DELETE FROM clearance_events WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
                (number,),
            )
            connection.execute(
                "DELETE FROM office_clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
                (number,),
            )
            connection.execute(
                "DELETE FROM clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
                (number,),
            )
            connection.execute("DELETE FROM students WHERE student_number = %s", (number,))
            connection.execute(
                "DELETE FROM rejected_records WHERE import_log_id IN (SELECT id FROM import_logs WHERE filename IN ('owed.csv', 'paid.csv'))"
            )
            connection.execute("DELETE FROM import_logs WHERE filename IN ('owed.csv', 'paid.csv')")
            connection.commit()


def _csv(student_number: str, assessed: str, paid: str, balance: str) -> str:
    return (
        "StudentNo,Name,Term,Assessed,Paid,Balance,LastPaymentDate\n"
        f"{student_number},\"Test, Student\",1S 2026-2027,{assessed},{paid},{balance},2026-10-01\n"
    )
