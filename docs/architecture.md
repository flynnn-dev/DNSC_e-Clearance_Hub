# Architecture

The browser talks only to the Flask Hub. Flask owns the session, the role check, and every database query. The browser never receives the database URL, the HMAC key, or the slip signing key.

```text
Browser  ->  Flask pages and /api  ->  Supabase Postgres
                |        |
                |        +-> Registrar mock (identity)
                +-> drop folder XML and CSV (Library and Accounting)
                +-> Nager.Date (Philippine public holidays)
```

## Offices

Registrar identifies the student. Library and Accounting are the offices that hold or sign off.

| Office status | Meaning |
| --- | --- |
| PENDING | Nothing blocking is imported, and nobody has signed off |
| HOLD | A blocking import is current, or staff placed a hold |
| CLEARED | Staff signed off, and nothing blocking is current |

Overall status is HOLD if either office is HOLD. It is CLEARED only when both are CLEARED. Otherwise it is PENDING.

A later blocking import returns that office to HOLD and revokes an open slip.

## Main folders

| Folder | Role |
| --- | --- |
| `app/auth` | Login, logout, session |
| `app/api` | Clearance, slips, reports |
| `app/importers` | Library XML, Accounting CSV, manifest HMAC |
| `app/services` | Clearance rules, slips, deadlines, reports |
| `app/integrations` | Registrar client and holiday client |
| `registrar_mock` | Instructor sample API |
| `drop` | Incoming, archive, rejected, logs |
| `samples` | Starter Library and Accounting files |

The original design note is `docs/phase-02-architecture.md`. This page is the system as it was built: Supabase Postgres, and the routes in `docs/api.md`.
