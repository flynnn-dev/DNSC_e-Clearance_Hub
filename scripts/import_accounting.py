"""Import one Accounting CSV export into the Hub."""

import os
import sys

from dotenv import load_dotenv

from app.config import BASE_DIR
from app.importers.accounting_csv import AccountingCsvError, import_accounting_file


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be the Supabase connection string.")
    if len(sys.argv) != 2:
        raise RuntimeError(
            "Usage: python -m scripts.import_accounting samples/accounting/accounting_balances_2026-11-20.csv"
        )
    try:
        result = import_accounting_file(database_url, sys.argv[1])
    except AccountingCsvError as exc:
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
