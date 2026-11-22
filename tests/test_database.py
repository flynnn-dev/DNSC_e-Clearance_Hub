"""The database engine is Supabase PostgreSQL."""

import os

import pytest
from dotenv import load_dotenv

from app.config import BASE_DIR
from app.db.postgres_repo import connection_string
from app.db.repository import ping


def test_blank_database_url_is_rejected():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        ping("")


def test_sqlite_url_is_rejected():
    with pytest.raises(RuntimeError, match="Supabase"):
        ping("sqlite:///instance/clearance.db")


def test_connection_string_requires_ssl():
    url = connection_string("postgresql://example.supabase.co/postgres")
    assert url.endswith("?sslmode=require")


def test_connection_string_keeps_existing_sslmode():
    url = "postgresql://example.supabase.co/postgres?sslmode=require"
    assert connection_string(url) == url


def test_supabase_ping_when_configured():
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        pytest.skip("Set DATABASE_URL to the Supabase connection string.")
    assert ping(database_url) is True
