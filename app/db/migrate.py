"""Create the approved Supabase tables. Running this again does not duplicate them."""

import os
from pathlib import Path

from dotenv import load_dotenv
from app.config import BASE_DIR
from app.db.postgres_repo import connect_postgres

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

TABLES = (
    "users",
    "students",
    "import_logs",
    "rejected_records",
    "library_records",
    "accounting_records",
    "office_clearance",
    "clearance",
    "clearance_events",
    "audit_logs",
    "clearance_tokens",
    "public_holidays",
    "holiday_fetch_logs",
)

CORE_TABLES = TABLES[:11]


def database_url_from_env() -> str:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase PostgreSQL connection string.")
    return database_url


def existing_tables(connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%s)
        """,
        (list(TABLES),),
    ).fetchall()
    return {row[0] for row in rows}


def statements_from_schema() -> list[str]:
    statements = []
    for part in SCHEMA_PATH.read_text(encoding="utf-8").split(";"):
        statement = part.strip()
        if statement:
            statements.append(statement)
    return statements


def apply_schema(database_url: str) -> str:
    with connect_postgres(database_url) as connection:
        present = existing_tables(connection)
        missing = set(TABLES) - present
        if not missing:
            return "already-applied"
        core_missing = set(CORE_TABLES) - present
        if present and core_missing:
            names = ", ".join(sorted(core_missing))
            raise RuntimeError(f"Supabase already has some Hub tables. Missing: {names}")
        for statement in statements_from_schema():
            if not present or any(name in statement for name in missing):
                connection.execute(statement)
        connection.commit()
    return "applied"


def main() -> None:
    result = apply_schema(database_url_from_env())
    print(result)


if __name__ == "__main__":
    main()
