"""Open the Supabase database. Table creation lives in app.db.migrate."""

from app.db.postgres_repo import ping_postgres


def ping(database_url: str) -> bool:
    if database_url.startswith(("postgresql://", "postgres://")):
        return ping_postgres(database_url)
    if database_url.startswith("sqlite:"):
        raise RuntimeError(
            "This project uses Supabase PostgreSQL. "
            "Set DATABASE_URL to the connection string from the Supabase dashboard."
        )
    raise RuntimeError("DATABASE_URL must start with postgresql://.")
