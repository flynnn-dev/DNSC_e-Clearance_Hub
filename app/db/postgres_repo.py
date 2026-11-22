"""Open Supabase PostgreSQL. Application tables are created only after the design is approved."""

import psycopg
from psycopg import Connection


def connection_string(database_url: str) -> str:
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL must start with postgresql://")
    if "sslmode=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}sslmode=require"


def connect_postgres(database_url: str) -> Connection:
    return psycopg.connect(
        connection_string(database_url),
        connect_timeout=5,
        prepare_threshold=None,
    )


def ping_postgres(database_url: str) -> bool:
    with connect_postgres(database_url) as connection:
        row = connection.execute("SELECT 1").fetchone()
        return row is not None and row[0] == 1
