"""Pull the Registrar masterlist into the Hub."""

import os
import sys

from dotenv import load_dotenv

from app.config import BASE_DIR
from app.integrations.registrar_client import RegistrarError
from app.services.registrar_sync import sync_masterlist


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    base_url = os.environ.get("REGISTRAR_BASE_URL", "").strip()
    api_key = os.environ.get("REGISTRAR_API_KEY", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase connection string.")
    try:
        result = sync_masterlist(database_url, base_url, api_key)
    except RegistrarError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"accepted={result['accepted']} rejected={result['rejected']}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
