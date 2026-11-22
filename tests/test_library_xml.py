"""Library XML rows follow the starter export."""

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR
from app.importers.library_xml import classify_borrowers, import_library_file, parse_library_xml

_SAMPLE = BASE_DIR / "samples" / "library" / "library_export_2026-11-20.xml"
_REGISTRAR = BASE_DIR / "registrar_mock" / "registrar_students.json"


def test_sample_export_keeps_known_students_and_rejects_planted_rows():
    known = {student["student_id"] for student in json.loads(_REGISTRAR.read_text(encoding="utf-8"))["students"]}
    rows = parse_library_xml(_SAMPLE.read_text(encoding="utf-8"))
    accepted, rejected = classify_borrowers(rows, known)
    reasons = {item["student_number"]: item["reason"] for item in rejected}
    assert len(rows) == 29
    assert len(accepted) == 25
    assert reasons["2026-1234"] == "studentNo must look like 2023-59928"
    assert reasons["2025-77777"] == "student is not in the Registrar masterlist"
    assert reasons["2024-99999"] == "lastBorrowed is not a real date"
    assert reasons["2023-59928"] == "unpaidFines must be zero or more, with at most two decimal places"
    blocking = {record["student_number"]: record["title"] for record in accepted if record["blocking"]}
    assert blocking["2025-81367"] == "1 unreturned book; unpaid fine 40.50"
    assert blocking["2026-61130"] == "1 unreturned book"
    assert blocking["2023-20570"] == "unpaid fine 10.00"
    clean = next(record for record in accepted if record["student_number"] == "2026-29417")
    assert clean["blocking"] is False
    assert clean["title"] == ""


def test_import_replaces_a_library_hold_when_the_next_file_is_clean():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    from app.db.postgres_repo import connect_postgres

    number = "2099-00008"
    folder = Path(os.environ["TEMP"]) / "dnsc-library-test"
    folder.mkdir(exist_ok=True)
    blocking = folder / "blocking.xml"
    clean = folder / "clean.xml"
    blocking.write_text(_xml(number, "1", "0.00"), encoding="utf-8")
    clean.write_text(_xml(number, "0", "0.00"), encoding="utf-8")
    with connect_postgres(database_url) as connection:
        connection.execute(
            """
            INSERT INTO students (student_number, display_name)
            VALUES (%s, 'Library Test')
            ON CONFLICT (student_number) DO NOTHING
            """,
            (number,),
        )
        connection.commit()
    try:
        assert import_library_file(database_url, blocking)["blocking"] == 1
        with connect_postgres(database_url) as connection:
            status = connection.execute(
                """
                SELECT office_clearance.status, clearance.overall_status
                FROM students
                JOIN office_clearance ON office_clearance.student_id = students.id AND office_clearance.office = 'library'
                JOIN clearance ON clearance.student_id = students.id
                WHERE students.student_number = %s
                """,
                (number,),
            ).fetchone()
            assert status == ("HOLD", "HOLD")
        assert import_library_file(database_url, clean)["blocking"] == 0
        with connect_postgres(database_url) as connection:
            status = connection.execute(
                """
                SELECT office_clearance.status, clearance.overall_status, library_records.is_blocking
                FROM students
                JOIN office_clearance ON office_clearance.student_id = students.id AND office_clearance.office = 'library'
                JOIN clearance ON clearance.student_id = students.id
                JOIN library_records ON library_records.student_id = students.id
                WHERE students.student_number = %s
                """,
                (number,),
            ).fetchone()
            assert status == ("PENDING", "PENDING", False)
    finally:
        with connect_postgres(database_url) as connection:
            connection.execute(
                """
                DELETE FROM library_records
                WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)
                """,
                (number,),
            )
            connection.execute(
                """
                DELETE FROM clearance_events
                WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)
                """,
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
                "DELETE FROM rejected_records WHERE import_log_id IN (SELECT id FROM import_logs WHERE filename IN ('blocking.xml', 'clean.xml'))"
            )
            connection.execute("DELETE FROM import_logs WHERE filename IN ('blocking.xml', 'clean.xml')")
            connection.commit()


def _xml(student_number: str, books: str, fine: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<borrowers exported="2026-11-20" branch="DNSC Main Library">
  <borrower card="LIB-TEST">
    <name>TEST, Student</name>
    <studentNo>{student_number}</studentNo>
    <program>BSIT</program>
    <yearLevel>1</yearLevel>
    <email>test@dnsc.edu.ph</email>
    <lastBorrowed>10/01/2026</lastBorrowed>
    <unreturnedBooks>{books}</unreturnedBooks>
    <unpaidFines>{fine}</unpaidFines>
  </borrower>
</borrowers>
"""
