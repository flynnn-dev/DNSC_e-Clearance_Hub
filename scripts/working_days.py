"""Print the date that is N Philippine working days after a start date."""

import os
import sys
from datetime import date

from dotenv import load_dotenv

from app.config import BASE_DIR
from app.services.deadline_service import DeadlineUnavailable, deadline_after


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase connection string.")
    if len(sys.argv) != 3:
        raise RuntimeError("Usage: python -m scripts.working_days 2026-11-20 5")
    try:
        start = date.fromisoformat(sys.argv[1])
        count = int(sys.argv[2])
    except ValueError as exc:
        raise RuntimeError("The start date must be YYYY-MM-DD and the count must be a whole number.") from exc
    try:
        result = deadline_after(database_url, start, count)
    except DeadlineUnavailable as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(result.isoformat())


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
