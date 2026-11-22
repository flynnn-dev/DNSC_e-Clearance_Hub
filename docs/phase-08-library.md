# DNSC e-Clearance Hub — Phase 8 Library XML

Status: a Library borrower export can be imported. Accounting is still pending. Staff sign-off is still a later phase.

The starter file is `samples/library/library_export_2026-11-20.xml`. Each `<borrower>` has `studentNo`, `unreturnedBooks`, and `unpaidFines`. There is no book-title tag, so the stored title is a label built from those two fields, such as `1 unreturned book; unpaid fine 40.50`. A clean borrower is stored with an empty title and does not block.

A row blocks Library when `unreturnedBooks` is greater than zero or `unpaidFines` is greater than zero. Fines are stored in centavos. That student’s Library office becomes HOLD, and the overall clearance becomes HOLD. A later file with no unreturned books and no fine replaces that row and returns Library to PENDING, unless a staff member’s own hold is still the latest hold. A clean file does not remove a staff sign-off.

These rows in the starter file are rejected, and the rest are saved:

- `2026-1234` is not a five-digit student number
- `2025-77777` is not in the Registrar masterlist
- `2024-99999` has `lastBorrowed` of `31/09/2026`
- the second `2023-59928` has a negative fine

Run:

```powershell
python -m scripts.import_library samples/library/library_export_2026-11-20.xml
```

The Accounting CSV and its manifest are saved in `samples/accounting/`. They are not imported in this phase. The manifest shows `sha256`, `nonce`, and `signature`, and the signature calculation is still Phase 13.
