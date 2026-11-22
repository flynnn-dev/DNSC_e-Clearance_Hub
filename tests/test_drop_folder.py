"""The drop folder archives a good file and rejects a replay or a broken file."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR
from app.services.drop_folder import process_drop_folder

_NUMBER = "2099-00031"


@pytest.fixture
def database_url():
    load_dotenv(BASE_DIR / ".env")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    return url


def test_good_library_file_is_archived_and_a_replay_is_rejected(database_url, tmp_path):
    from app.db.postgres_repo import connect_postgres

    _student(database_url)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    xml = incoming / "phase11-library.xml"
    xml.write_text(_xml(_NUMBER, "1", "0.00"), encoding="utf-8")
    try:
        first = process_drop_folder(database_url, tmp_path)
        assert first[0]["result"] == "archived"
        assert not xml.exists()
        assert (tmp_path / "archive" / "phase11-library.xml").is_file()
        archived = (tmp_path / "archive" / "phase11-library.xml").read_bytes()
        replay = incoming / "phase11-library.xml"
        replay.write_bytes(archived)
        second = process_drop_folder(database_url, tmp_path)
        assert second[0]["result"] == "rejected"
        assert second[0]["detail"] == "This file was already imported."
        assert (tmp_path / "rejected" / "phase11-library.xml").is_file()
        with connect_postgres(database_url) as connection:
            status = connection.execute(
                """
                SELECT status FROM office_clearance
                WHERE office = 'library'
                  AND student_id = (SELECT id FROM students WHERE student_number = %s)
                """,
                (_NUMBER,),
            ).fetchone()
            assert status[0] == "HOLD"
    finally:
        _cleanup(database_url)


def test_broken_xml_and_a_bad_manifest_go_to_rejected(database_url, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "phase11-broken.xml").write_text("<not-library>", encoding="utf-8")
    csv_path = incoming / "phase11-bad.csv"
    csv_path.write_text(_csv(_NUMBER, "100.00", "100.00", "0.00"), encoding="utf-8")
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    (incoming / "phase11-bad.csv.manifest.json").write_text(
        json.dumps({
            "file": "phase11-bad.csv",
            "source": "accounting",
            "sha256": "0" * 64,
            "record_count": 1,
            "nonce": "phase11-bad-nonce",
        }),
        encoding="utf-8",
    )
    try:
        results = process_drop_folder(database_url, tmp_path)
        by_name = {item["file"]: item["result"] for item in results}
        assert by_name["phase11-broken.xml"] == "rejected"
        assert by_name["phase11-bad.csv"] == "rejected"
        assert "signature" in next(item["detail"] for item in results if item["file"] == "phase11-bad.csv")
        assert digest != "0" * 64
        assert (tmp_path / "rejected" / "phase11-broken.xml").is_file()
        assert (tmp_path / "rejected" / "phase11-bad.csv").is_file()
        assert not any(incoming.iterdir())
    finally:
        _cleanup(database_url)


def _student(database_url: str) -> None:
    from app.db.postgres_repo import connect_postgres

    with connect_postgres(database_url) as connection:
        connection.execute(
            """
            INSERT INTO students (student_number, display_name)
            VALUES (%s, 'Drop Folder Test')
            ON CONFLICT (student_number) DO NOTHING
            """,
            (_NUMBER,),
        )
        connection.commit()


def _cleanup(database_url: str) -> None:
    from app.db.postgres_repo import connect_postgres

    with connect_postgres(database_url) as connection:
        connection.execute(
            "DELETE FROM library_records WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM accounting_records WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM clearance_events WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM office_clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute(
            "DELETE FROM clearance WHERE student_id IN (SELECT id FROM students WHERE student_number = %s)",
            (_NUMBER,),
        )
        connection.execute("DELETE FROM students WHERE student_number = %s", (_NUMBER,))
        connection.execute(
            "DELETE FROM import_logs WHERE filename LIKE 'phase11-%'"
        )
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


def _csv(student_number: str, assessed: str, paid: str, balance: str) -> str:
    return (
        "StudentNo,Name,Term,Assessed,Paid,Balance,LastPaymentDate\n"
        f"{student_number},\"Test, Student\",1S 2026-2027,{assessed},{paid},{balance},2026-10-01\n"
    )
