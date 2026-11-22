# DNSC e-Clearance Hub — Phase 7 Registrar sync

Status: the Hub can read the instructor's mock Registrar API and store the masterlist. Library and Accounting imports are still empty, so clearance stays pending.

The mock server is `registrar_mock/registrar_mock_api.py`. It is the instructor's script. It reads `registrar_mock/registrar_students.json`. That starter list is in the repo: 40 synthetic students, each with `student_id` like `2026-29417`.

Start the mock in one terminal:

```powershell
$env:REGISTRAR_API_KEY = "your-own-key"
python registrar_mock/registrar_mock_api.py
```

Put the same key in `.env` as `REGISTRAR_API_KEY`. `REGISTRAR_BASE_URL` is `http://127.0.0.1:8001`. Then, in another terminal:

```powershell
python -m scripts.sync_registrar
```

The client sends `X-API-Key`, pages with `size=20`, and retries HTTP 503 using the `Retry-After` header (capped at 5 seconds, four tries). A failed fetch writes a rejected import log and leaves students already in the database alone.

A valid `student_id` is stored as `students.student_number`. The rest of the object is stored in `registrar_payload`. The display name is the first of `full_name`, `name`, `student_name`, or `display_name`. The starter list has no single name field, so the Hub joins `first_name`, `middle_initial`, and `last_name` (for example, Mark D Navarro). If none of those exist, the display name is the student id. A bad id is stored in `rejected_records` instead of `students`.

A new student gets a pending Library row, a pending Accounting row, and a pending overall clearance row. A later sync updates the name and payload only. It does not change HOLD or CLEARED.
