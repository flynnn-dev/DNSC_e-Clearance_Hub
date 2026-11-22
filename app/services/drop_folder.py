"""Import files from drop/incoming, then move them to archive or rejected."""

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

from app.db.postgres_repo import connect_postgres
from app.importers.accounting_csv import AccountingCsvError, import_accounting_file
from app.importers.library_xml import LibraryXmlError, import_library_file


class DropFolderError(Exception):
    """The drop folder could not be processed."""


def process_drop_folder(database_url: str, root: str | Path) -> list[dict]:
    folder = Path(root)
    incoming = folder / "incoming"
    archive = folder / "archive"
    rejected = folder / "rejected"
    for path in (incoming, archive, rejected, folder / "logs"):
        path.mkdir(parents=True, exist_ok=True)
    results = []
    files = sorted(
        path for path in incoming.iterdir()
        if path.is_file() and not path.name.startswith(".") and not path.name.endswith(".manifest.json")
    )
    for path in files:
        results.append(_process_one(database_url, path, archive, rejected))
    _write_log(folder / "logs", results)
    return results


def _process_one(database_url: str, path: Path, archive: Path, rejected: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".xml":
        source = "library_xml"
        importer = import_library_file
        error_type = LibraryXmlError
    elif suffix == ".csv":
        source = "accounting_csv"
        importer = import_accounting_file
        error_type = AccountingCsvError
    else:
        destination = _move(path, rejected)
        return {"file": path.name, "result": "rejected", "detail": "The drop folder accepts .xml and .csv files.", "moved_to": str(destination)}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    nonce = _manifest_nonce(path)
    if _already_imported(database_url, source, digest, nonce):
        _remember_rejection(database_url, source, path.name, digest, "This file was already imported.")
        destination = _move(path, rejected, _manifest_path(path))
        return {"file": path.name, "result": "rejected", "detail": "This file was already imported.", "moved_to": str(destination)}
    try:
        outcome = importer(database_url, path)
    except error_type as exc:
        destination = _move(path, rejected, _manifest_path(path))
        return {"file": path.name, "result": "rejected", "detail": str(exc), "moved_to": str(destination)}
    destination = _move(path, archive, _manifest_path(path))
    detail = f"accepted={outcome['accepted']} rejected={outcome['rejected']}"
    return {"file": path.name, "result": "archived", "detail": detail, "moved_to": str(destination)}


def _manifest_path(path: Path) -> Path | None:
    sidecar = Path(str(path) + ".manifest.json")
    if sidecar.is_file():
        return sidecar
    return None


def _manifest_nonce(path: Path) -> str | None:
    sidecar = _manifest_path(path)
    if sidecar is None:
        return None
    import json
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    nonce = data.get("nonce") if isinstance(data, dict) else None
    if isinstance(nonce, str) and nonce.strip():
        return nonce.strip()
    return None


def _already_imported(database_url: str, source: str, digest: str, nonce: str | None) -> bool:
    with connect_postgres(database_url) as connection:
        row = connection.execute(
            """
            SELECT 1 FROM import_logs
            WHERE status = 'accepted'
              AND source = %s
              AND file_sha256 = %s
            """,
            (source, digest),
        ).fetchone()
        if row is not None:
            return True
        if not nonce:
            return False
        row = connection.execute(
            """
            SELECT 1 FROM import_logs
            WHERE status = 'accepted' AND manifest_id = %s
            """,
            (nonce,),
        ).fetchone()
    return row is not None


def _remember_rejection(database_url: str, source: str, filename: str, digest: str, message: str) -> None:
    with connect_postgres(database_url) as connection:
        connection.execute(
            """
            INSERT INTO import_logs (source, filename, file_sha256, status, rows_accepted, rows_rejected, message)
            VALUES (%s, %s, %s, 'rejected', 0, 0, %s)
            """,
            (source, filename, digest, message),
        )
        connection.commit()


def _move(path: Path, folder: Path, sidecar: Path | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    destination = _available(folder, path.name)
    shutil.move(str(path), str(destination))
    if sidecar is not None and sidecar.is_file():
        shutil.move(str(sidecar), str(_available(folder, sidecar.name)))
    return destination


def _available(folder: Path, name: str) -> Path:
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = Path(name)
    return folder / f"{path.stem}-{stamp}{path.suffix}"


def _write_log(folder: Path, results: list[dict]) -> None:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    lines = [f"{item['result']} {item['file']} {item['detail']}" for item in results]
    if not lines:
        lines = ["No files were waiting in incoming."]
    (folder / f"{stamp}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
