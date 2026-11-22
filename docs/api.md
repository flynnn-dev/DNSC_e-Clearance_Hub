# Hub API

Base URL on this computer: `http://127.0.0.1:5000`.

The browser session cookie is sent automatically. POST requests also need the CSRF token from the page, in the form field `csrf_token` or the header `X-CSRF-Token`.

A visitor who is not signed in receives `401` and `{"error": "Sign in required."}` on an API path. The wrong role receives `403`.

A Postman collection of these calls is in `postman/DNSC-e-Clearance-Hub.postman_collection.json`.

## Auth

| Method and path | Who | Result |
| --- | --- | --- |
| `POST /api/auth/login` | Public | Starts a session. Form fields: `email`, `password`, `csrf_token`. |
| `POST /api/auth/logout` | Signed in | Ends the session. |
| `GET /api/auth/me` | Signed in | Email, role, and office. |

A wrong email or password returns `401`. The password is not echoed.

## Student

| Method and path | Who | Result |
| --- | --- | --- |
| `GET /api/me/clearance` | Student | The linked student only. A student id in the query string is ignored. Also returns `deadline` or `deadline_error`. The date does not change office status. |
| `POST /api/me/slip` | Student | Issues a slip when the overall status is `CLEARED`. |

The slip response contains `verify_path`, `expires_at`, and `qr_svg`. The slip lasts 14 calendar days.

## Public slip check

| Method and path | Who | Result |
| --- | --- | --- |
| `GET /api/verify/<token>` | Public | Signature, expiry, and current clearance. Masked student number. |
| `GET /verify/<token>` | Public | The same check as a page. |

The JSON does not include the name, a fine, a book title, or a balance.

## Staff

The office is the office stored on the staff user. The client cannot choose a different office.

| Method and path | Who | Result |
| --- | --- | --- |
| `GET /api/staff/clearance` | Staff | Students, status, and hold reason for that office. |
| `POST /api/staff/clearance/<student_number>/hold` | Staff | Hold. JSON body `reason`, 1 to 500 characters. |
| `POST /api/staff/clearance/<student_number>/signoff` | Staff | Sign off. `409` when a blocking record is still there. |
| `GET /api/office/reports.json` | Staff | Masked student numbers, name, status, reason, and counts. |
| `GET /api/office/reports.csv` | Staff | The same rows as a CSV download. |

`<student_number>` must look like `2023-24935`. Anything else is `404`.

## Health

`GET /health` returns `{"status": "ok"}`.
