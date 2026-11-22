# Installation

These steps are for Windows PowerShell. The commands use the project folder.

## 1. Install the Python packages

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Build the CSS

```powershell
npm install
npm run css:build
```

Node builds the stylesheet only. The running site is Flask.

## 3. Fill in `.env`

```powershell
copy .env.example .env
```

Set these values in `.env`. Leave them empty in `.env.example`.

| Name | What it is |
| --- | --- |
| `SECRET_KEY` | Flask session key |
| `DATABASE_URL` | Supabase Postgres connection string |
| `REGISTRAR_BASE_URL` | `http://127.0.0.1:8001` when the mock API is local |
| `REGISTRAR_API_KEY` | The same key you pass to the mock API |
| `HMAC_SECRET` | Key for import manifest signatures |
| `SLIP_SIGNING_KEY` | Key for clearance slips |
| `SEED_STUDENT_EMAIL` | Student demo email |
| `SEED_STUDENT_PASSWORD` | Student demo password |
| `SEED_STAFF_EMAIL` | Staff demo email |
| `SEED_STAFF_PASSWORD` | Staff demo password |
| `SEED_STAFF_OFFICE` | `library` or `accounting` |
| `SEED_STUDENT_NUMBER` | Optional student number to link to the student login |

`.env` stays off Git.

## 4. Create the tables and the demo accounts

```powershell
python -m app.db.migrate
python -m scripts.seed_users
```

`migrate` prints `applied` the first time and `already-applied` after that. `seed_users` prints `demo-accounts-ready`.

## 5. Start the Registrar mock

Use the same API key as `REGISTRAR_API_KEY`.

```powershell
$env:REGISTRAR_API_KEY = "<the key in .env>"
$env:PORT = "8001"
python registrar_mock\registrar_mock_api.py
```

Leave that window open. In another window:

```powershell
python -m scripts.sync_registrar
```

A good run prints `accepted=40 rejected=0`.

## 6. Import the starter files

```powershell
python -m scripts.import_library samples\library\library_export_2026-11-20.xml
python -m scripts.import_accounting samples\accounting\accounting_balances_2026-11-20.csv
```

The Accounting import checks the manifest signature before it reads rows. `HMAC_SECRET` must be the key that signed that file.

Later files can be dropped in `drop\incoming` and imported with:

```powershell
python -m scripts.process_drop_folder
```

## 7. Start the Hub

```powershell
python -m flask --app app run --port 5000
```

Open http://127.0.0.1:5000.

## Working-day check

```powershell
python -m scripts.working_days 2026-11-20 5
```

This prints a date. It is not attached to a clearance yet.
