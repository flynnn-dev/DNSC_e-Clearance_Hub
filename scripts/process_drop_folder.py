"""Import every Library XML and Accounting CSV waiting in drop/incoming."""

import os
import sys

from dotenv import load_dotenv

from app.config import BASE_DIR
from app.services.drop_folder import DropFolderError, process_drop_folder


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase connection string.")
    try:
        results = process_drop_folder(database_url, BASE_DIR / "drop")
    except DropFolderError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    if not results:
        print("processed=0")
        return
    for item in results:
        print(f"{item['result']} {item['file']} {item['detail']}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
