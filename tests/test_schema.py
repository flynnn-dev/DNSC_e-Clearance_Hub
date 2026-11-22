"""The approved tables exist on Supabase and reject bad rows."""

import os

import psycopg
import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR
from app.db.migrate import TABLES, apply_schema, existing_tables
from app.db.postgres_repo import connect_postgres


@pytest.fixture
def database_url():
    load_dotenv(BASE_DIR / ".env")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    return url


def test_schema_creates_the_approved_tables(database_url):
    assert apply_schema(database_url) in {"applied", "already-applied"}
    with connect_postgres(database_url) as connection:
        assert existing_tables(connection) == set(TABLES)


def test_staff_and_student_office_rules(database_url):
    apply_schema(database_url)
    with connect_postgres(database_url) as connection:
        try:
            _expect_check(
                connection,
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, 'staff')
                """,
                ("staff-without-office@example.com", "hash"),
            )
            _expect_check(
                connection,
                """
                INSERT INTO users (email, password_hash, role, office)
                VALUES (%s, %s, 'student', 'library')
                """,
                ("student-with-office@example.com", "hash"),
            )
        finally:
            connection.rollback()


def test_email_unique_ignores_case(database_url):
    apply_schema(database_url)
    with connect_postgres(database_url) as connection:
        try:
            connection.execute(
                """
                INSERT INTO users (email, password_hash, role, office)
                VALUES (%s, %s, 'staff', 'library')
                """,
                ("library-case@example.com", "hash"),
            )
            with pytest.raises(psycopg.errors.UniqueViolation):
                connection.execute(
                    """
                    INSERT INTO users (email, password_hash, role, office)
                    VALUES (%s, %s, 'staff', 'accounting')
                    """,
                    ("LIBRARY-case@example.com", "hash"),
                )
        finally:
            connection.rollback()


def test_library_row_requires_real_student_and_import(database_url):
    apply_schema(database_url)
    with connect_postgres(database_url) as connection:
        try:
            student_id = connection.execute(
                """
                INSERT INTO students (student_number, display_name)
                VALUES (%s, %s)
                RETURNING id
                """,
                ("2026-FK", "Foreign Key Test"),
            ).fetchone()[0]
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                connection.execute(
                    """
                    INSERT INTO library_records (
                        student_id, import_log_id, is_unreturned, fine_cents, is_blocking, source_payload
                    )
                    VALUES (%s, 999999, TRUE, 0, TRUE, '{}'::jsonb)
                    """,
                    (student_id,),
                )
        finally:
            connection.rollback()


def test_cleared_office_requires_signoff(database_url):
    apply_schema(database_url)
    with connect_postgres(database_url) as connection:
        try:
            student_id = connection.execute(
                """
                INSERT INTO students (student_number, display_name)
                VALUES (%s, %s)
                RETURNING id
                """,
                ("2026-CLEAR", "Clearance Rule Test"),
            ).fetchone()[0]
            with pytest.raises(psycopg.errors.CheckViolation):
                connection.execute(
                    """
                    INSERT INTO office_clearance (student_id, office, status)
                    VALUES (%s, 'library', 'CLEARED')
                    """,
                    (student_id,),
                )
        finally:
            connection.rollback()


def test_accepted_manifest_cannot_be_reused(database_url):
    apply_schema(database_url)
    with connect_postgres(database_url) as connection:
        try:
            connection.execute(
                """
                INSERT INTO import_logs (source, manifest_id, status)
                VALUES ('library_xml', %s, 'accepted')
                """,
                ("constraint-manifest",),
            )
            with pytest.raises(psycopg.errors.UniqueViolation):
                connection.execute(
                    """
                    INSERT INTO import_logs (source, manifest_id, status)
                    VALUES ('library_xml', %s, 'accepted')
                    """,
                    ("constraint-manifest",),
                )
        finally:
            connection.rollback()


def _expect_check(connection, statement: str, params: tuple) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(statement, params)
    connection.rollback()
