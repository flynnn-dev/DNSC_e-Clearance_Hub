"""Create or update the demo accounts from .env. Passwords are stored as hashes."""

import os
import sys

from dotenv import load_dotenv

from app.config import BASE_DIR
from app.db.postgres_repo import connect_postgres
from app.db.users import save_user
from app.security.passwords import hash_password

_ROLES = {
    "student": None,
    "staff": {"library", "accounting"},
}


def seed(database_url: str) -> None:
    accounts = (
        _account("SEED_STUDENT_EMAIL", "SEED_STUDENT_PASSWORD", "student", None),
        _account(
            "SEED_STAFF_EMAIL",
            "SEED_STAFF_PASSWORD",
            "staff",
            os.environ.get("SEED_STAFF_OFFICE", "").strip().lower(),
        ),
    )
    with connect_postgres(database_url) as connection:
        for email, password, role, office in accounts:
            save_user(connection, email, hash_password(password), role, office)
        student_number = os.environ.get("SEED_STUDENT_NUMBER", "").strip()
        if student_number:
            _link_student(connection, accounts[0][0], student_number)
        connection.commit()


def _account(email_key: str, password_key: str, role: str, office: str | None):
    email = os.environ.get(email_key, "").strip().lower()
    password = os.environ.get(password_key, "")
    if not email or not password:
        raise RuntimeError(f"{email_key} and {password_key} must be set in .env.")
    if role == "student" and office is not None:
        raise RuntimeError("A student account cannot have an office.")
    if role == "staff" and office not in _ROLES["staff"]:
        raise RuntimeError("SEED_STAFF_OFFICE must be library or accounting.")
    return email, password, role, office


def _link_student(connection, email: str, student_number: str) -> None:
    user = connection.execute(
        "SELECT id FROM users WHERE lower(email) = lower(%s)",
        (email,),
    ).fetchone()
    student = connection.execute(
        "SELECT id FROM students WHERE student_number = %s",
        (student_number,),
    ).fetchone()
    if user is None or student is None:
        raise RuntimeError("SEED_STUDENT_NUMBER must already exist in the Registrar masterlist.")
    connection.execute(
        "UPDATE students SET user_id = NULL WHERE user_id = %s AND id <> %s",
        (user[0], student[0]),
    )
    connection.execute(
        "UPDATE students SET user_id = %s WHERE id = %s",
        (user[0], student[0]),
    )


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase connection string.")
    seed(database_url)
    print("demo-accounts-ready")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
