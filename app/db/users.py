"""User rows. Queries are parameterized."""

from psycopg.rows import dict_row

from app.db.postgres_repo import connect_postgres


def connect():
    from flask import current_app

    return connect_postgres(current_app.config["DATABASE_URL"])


def find_user_by_email(connection, email: str):
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, email, password_hash, role, office
            FROM users
            WHERE lower(email) = lower(%s)
            """,
            (email,),
        ).fetchone()


def find_user_by_id(connection, user_id: int):
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id, email, password_hash, role, office
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        ).fetchone()


def save_user(connection, email: str, password_hash: str, role: str, office: str | None) -> None:
    existing = find_user_by_email(connection, email)
    if existing is None:
        connection.execute(
            """
            INSERT INTO users (email, password_hash, role, office)
            VALUES (%s, %s, %s, %s)
            """,
            (email, password_hash, role, office),
        )
        return
    connection.execute(
        """
        UPDATE users
        SET password_hash = %s, role = %s, office = %s
        WHERE id = %s
        """,
        (password_hash, role, office, existing["id"]),
    )
