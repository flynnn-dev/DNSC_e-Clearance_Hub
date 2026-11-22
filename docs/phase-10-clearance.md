# DNSC e-Clearance Hub — Phase 10 Clearance processing

Status: a student can read the clearance linked to their login. Library or Accounting staff can place a hold or sign off, and only for their own office. The downloadable slip is still disabled.

`GET /api/me/clearance` uses the signed-in student. A student number in the query string is ignored. If `students.user_id` is empty, the page says the account is not linked. Set `SEED_STUDENT_NUMBER` in `.env` to a number from the Registrar list, then run `python -m scripts.seed_users`, to attach the demo student login.

`GET /api/staff/clearance` lists every student for the staff member's office. A blocking Library or Accounting row disables Sign off. The server refuses that sign-off with HTTP 409 even if the button is bypassed. Place on hold requires a reason, records the staff user, and sets the overall status to HOLD when either office is on hold. Both actions write a history row and an audit row.

The student page and the staff page load this data with JavaScript from those Hub routes. The browser still does not open Supabase.
