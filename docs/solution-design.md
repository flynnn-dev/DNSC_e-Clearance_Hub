# Solution design

This is the short design note for the individual Track A Hub. The built system is described in [architecture.md](architecture.md). This page records the problem, the people, the data flow, and why the signed QR slip is the emerging-technology piece.

## Problem

A student used to carry a paper clearance form to the Library and to Accounting. Each office checked its own records. A lost form meant starting over, and the offices could not share one status because their files are different: Registrar uses JSON, the Library uses XML, and Accounting uses CSV.

The Hub does not replace those offices. It reads them and shows one clearance.

## Stakeholders

- Students sign in and read their own status, the hold reason, and a signed slip.
- Library staff and Accounting staff each see only their own office. They place a hold or sign off.
- The Registrar stays the source of the student list. There is no Registrar login in this version.
- Student Affairs and an admin role are outside the individual scope.

## Architecture

The browser talks only to the Flask Hub. Flask checks the session and runs the queries. The database is Supabase PostgreSQL. The browser never receives the database URL or the signing keys.

```text
Browser  ->  Flask pages and /api  ->  Supabase Postgres
                |        |
                |        +-> Registrar mock (identity)
                +-> drop folder XML and CSV (Library and Accounting)
                +-> Nager.Date (Philippine public holidays)
```

## Data flow

1. The Registrar sync copies the student number, name, and program into the Hub. That student number is the join key.
2. The drop-folder script reads a Library XML file and an Accounting CSV file. Each row is mapped into the common clearance records. A bad row is logged and skipped. An Accounting manifest is checked before any row is read.
3. An office is PENDING until a sign-off, HOLD when a blocking record or a staff hold is current, and CLEARED when staff sign off and nothing blocking remains.
4. Overall status is HOLD if either office is HOLD, CLEARED only when both are CLEARED, and PENDING otherwise.
5. The student page reads `GET /api/me/clearance`. The deadline on that page is a working-day count from `CLEARANCE_ANCHOR_DATE`. It does not change the office status. If the holiday list was never saved, the page says the deadline is unavailable.

## Emerging technology

The signed QR clearance slip is the one emerging-technology piece for this individual project.

A slip is issued only when both offices are CLEARED. The QR encodes a signed token, not the student's name or balance. Any phone can open the public check. The check confirms the signature and the current clearance, and it shows a masked student number. A later hold revokes the slip, so an old QR cannot be reused as proof.

A full installable app was not chosen. The signed slip is the part a student can carry and an office can verify without opening the student account.
