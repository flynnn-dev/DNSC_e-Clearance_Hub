"""Import one Library XML export into the Hub."""

import os
import sys

from dotenv import load_dotenv

from app.config import BASE_DIR
from app.importers.library_xml import LibraryXmlError, import_library_file


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase connection string.")
    if len(sys.argv) != 2:
        raise RuntimeError("Usage: python -m scripts.import_library samples/library/library_export_2026-11-20.xml")
    try:
        result = import_library_file(database_url, sys.argv[1])
    except LibraryXmlError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        f"accepted={result['accepted']} rejected={result['rejected']} blocking={result['blocking']}"
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
