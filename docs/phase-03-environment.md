# DNSC e-Clearance Hub — Phase 3 Environment

Status: environment checked. Login, database tables, and imports are not part of this phase.
This setup follows [phase-02-architecture.md](phase-02-architecture.md).

## What is installed

| Tool | Version used |
| --- | --- |
| Python | 3.15.2 |
| Flask | 3.1.3 |
| python-dotenv | 1.2.4 |
| pytest | 9.2.0 |
| Node.js | 26.13.1 |
| Tailwind CSS | 4.3.5 |
| Git | 2.56.1 |

Direct Python packages are pinned in `requirements.txt`. Tailwind is a build tool in `package.json`. Node is not a second backend.

## Create the environment again

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
npm run css:build
copy .env.example .env
```

Set `SECRET_KEY` in `.env` to a long random value. The application refuses to start when `SECRET_KEY` is empty. Demo account values, when you add them, stay in `.env` only.

## Run and test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m flask --app app run --port 5000
```

Checked results:

- `pytest`: 3 passed.
- `GET /health` returns `{"status": "ok"}`.
- `GET /` shows DNSC e-Clearance Hub with the Tailwind stylesheet.
- `.env`, `.venv/`, and `node_modules/` are ignored by Git.

The local `.env` already has a generated `SECRET_KEY` and the Phase 1 demo account values. It is not committed.

## What this phase does not do

- No login page and no password check.
- No database connection and no tables.
- No Registrar, XML, CSV, or holiday calls.
- `python -m scripts.seed_users`, `python -m scripts.sync_registrar`, and `python -m scripts.process_drop_folder` stop with a message naming the phase that implements them.

Phase 4 database design is recorded in [phase-04-database.md](phase-04-database.md).
