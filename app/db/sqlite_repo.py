"""SQLite is not the engine for this project."""


def ping_sqlite(database_url: str) -> bool:
    raise RuntimeError(
        "This project uses Supabase PostgreSQL. "
        "Set DATABASE_URL to the connection string from the Supabase dashboard."
    )
