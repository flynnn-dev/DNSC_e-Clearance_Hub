# DNSC e-Clearance Hub — Phase 1 Requirements Baseline

Status: accepted baseline. No application code in this phase.
Phase 2 architecture is recorded in [phase-02-architecture.md](phase-02-architecture.md).

This document records the individual-project scope, the architecture decisions that later phases must follow, the demo accounts, and the questions still open with the instructor.

Sources used:

- The project brief provided in the working session.
- An empty workspace at the time of analysis: no official PDF, mock API documentation, sample Library XML, or sample Accounting CSV was in the project folder.

Anything not in that brief is marked **confirm**. It is not assumed.

## Architect decisions

The build stays one Hub that integrates Registrar, Library, and Accounting. It does not rebuild those offices. Later phases follow the existing 16-phase sequence, with these decisions fixed:

1. **Schema stays provisional until source files exist.** Phase 4 may propose tables. Columns are locked only after the Registrar mock API docs plus sample Library XML and Accounting CSV are in the repo. The join key (student number or equivalent) must be the same field across all three sources.
2. **Supabase is hosted PostgreSQL behind Flask, or SQLite behind the same data-access layer.** The browser never talks to Supabase. No service-role key in frontend code. Flask owns authentication, queries, and role checks. If the instructor requires SQLite, only the database adapter changes.
3. **Emerging technology is a signed QR clearance slip**, plus the mobile-responsive UI already required. A full PWA is extra scope and is not the default.
4. **Pytest starts with the first real module** (authentication, then importers). Phase 15 is the evidence pack and regression run.

The individual scope has no admin UI. A one-time seed script creates the demo logins in this document. It is a setup tool, not an admin product.

The client is Jinja shells plus JavaScript that reads and writes only the Hub REST API. Clearance data is not rendered by querying the database inside templates.

## 1. Required individual features

### Student

- Log in and log out.
- View own profile (from the Registrar masterlist).
- View overall clearance status.
- View status per office that is in individual scope.
- View HOLD reasons.
- View own clearance history.
- Download or verify a digital clearance slip.

### Staff

- Log in and log out.
- See only the office they are assigned to.
- Review student clearance information for that office.
- Place a HOLD with a reason.
- Approve or sign off that office.
- View that office's clearance records.

Login users are students and staff only.

### Offices in the integration

These systems are read by the Hub. They are not rebuilt, and they are not extra user accounts.

- Registrar: pull the official student masterlist from the instructor's mock REST API.
- Library: import borrowed books, unreturned books, and unpaid fines from XML via the drop folder.
- Accounting: import tuition and other balances from CSV via the drop folder.
- The Hub computes clearance from those records.

### Automation

- Process a shared drop folder.
- Run the XML importer and the CSV importer.
- Write timestamped logs.
- Move successfully processed files into an archive.
- Reject invalid rows, log the reason, and keep going.

### API and calendar

- The Hub REST API is the only data path for the student and staff UI.
- Registrar client: timeouts, HTTP errors, and invalid JSON.
- Nager.Date for Philippine public holidays.
- Deadline math in working days, excluding weekends and Philippine public holidays, with a defined failure behavior when the holiday API is down.

### Data mapping and security

- One common clearance schema mapped from Registrar JSON, Library XML, and Accounting CSV.
- Validate imports; log rejected records and reasons.
- CSV and JSON reports.
- Password hashing with PBKDF2 or bcrypt.
- Flask sessions or secure tokens.
- Role checks on the server for student vs staff, and staff limited to their office.
- Parameterized SQL only.
- Secrets in environment variables, never in source and never in the browser.
- HMAC verification of import manifests; reject tampered files and replays.
- Signed clearance verification token (QR or short code plus a verify endpoint).
- Mask student IDs on public reports.
- Audit log for holds and sign-offs.

### Quality

- Responsive UI on desktop, laptop, tablet, and phone. Mobile-first. No horizontal overflow. Usable tables, cards, forms, and modals.
- Accessible forms, labels, focus, contrast, and status messages.
- Tailwind CSS only. No Bootstrap. Lucide icons. Navy, white, and neutral UI.
- Pytest coverage for mapping, API, authentication, authorization, SQL injection resistance, tampered imports, expired tokens, and wrong-role access.
- A Postman (or equivalent) collection for the Hub API.
- Git with a remote on GitHub. Secrets stay out of the repository.

## 2. Optional individual features

- Supabase PostgreSQL, if the instructor approves. Otherwise SQLite, with the same application structure.
- QR slip as the emerging-technology piece (the default).
- PWA installability, only if QR is rejected or time remains after the required modules pass.
- A daily per-office HOLD summary, only if the approved individual brief requires it.
- A development seed script that creates the two demo accounts below. A second staff account, for the other office, is added when both Library and Accounting sign-off are tested.

## 3. Out of scope unless the instructor puts them back

- Rebuilding Registrar, Library, or Accounting.
- A Student Affairs office.
- A separate admin role and admin screens.
- Any endpoint, column, or sample value that is not in the instructor's API docs or sample files.
- An in-app survey product for the 30 raters. That evaluation is an activity, not a Hub module, unless the brief says otherwise.

## 4. Technical requirements

- Python 3, Flask, Blueprints, and REST.
- Server-rendered Jinja for layout. JavaScript for all Hub data.
- Tailwind via its CLI. Node is a build tool only, not a second backend.
- HTTP with `requests`. XML with ElementTree. CSV with the stdlib `csv` module.
- PostgreSQL via Supabase, or SQLite. One repository boundary so a database swap does not rewrite routes or UI.
- Authorization enforced in Flask, not by hiding buttons.
- Input allow-lists. Generic error responses to clients. Details stay in server logs.
- Normalized tables, created only after the database design is approved. Proposed names to revisit against the real files: `users`, `students`, `office_records`, `library_records`, `accounting_records`, `clearance`, `office_clearance`, `import_logs`, `rejected_records`, `audit_logs`, `clearance_tokens`. Merge or drop any table that would duplicate a source record.

**Working clearance rule (confirm with the instructor):** a student is cleared overall only when every required office is signed off and no imported hold condition remains. Any office HOLD, or any blocking library or accounting condition, keeps the overall status on HOLD. The reasons are visible to that student and to the responsible staff.

**Office split (confirm with the instructor):** Registrar supplies identity. Library and Accounting are the offices that can HOLD and sign off. Each staff user belongs to one of those two offices.

### Demo accounts

Decided for local testing. Created in Phase 6 by a seed script, after the database exists.

| Role | Email | Password | Office |
| --- | --- | --- | --- |
| Student | `user@gmail.com` | `user123` | — |
| Staff | `staff@gmail.com` | `staff123` | Library, until an Accounting staff account is added |

Storage rules:

- The database stores a PBKDF2 or bcrypt hash only.
- Plain passwords live in a local `.env` file that Git does not commit.
- Source code, templates, and the committed `.env.example` do not contain these passwords.
- These logins are for a local machine and a class demo. They are not for a public server.

## 5. Deliverables and evaluation

- A working Hub for student and staff.
- A solution design write-up: stakeholders, problem, architecture, data flow, and digital-transformation benefits (Phase 2 and Phase 16).
- API documentation.
- Import adapters, a drop-folder script, logs, and archive behavior.
- Security evidence: hashing, role-based access, parameterized queries, HMAC, replay rejection, a signed slip, ID masking, and an audit log.
- Test evidence: pytest output, an API collection, security cases, and responsive checks.
- A user evaluation with 30 external raters, plus the instrument and results the brief asks for.
- README, installation guide, architecture note, user manual, and defense explanation.

## Phase map

Each required item is implemented in a later phase. This list is the gate. A feature that is not required waits.

| Phase | Work |
| --- | --- |
| 2 | Architecture diagram, data flow, security boundaries, folder layout |
| 3 | Python, Flask, Tailwind, Git, environment variables |
| 4 | Database design and connectivity, after schema approval |
| 5 | Design system, responsive navigation, login and dashboard layouts |
| 6 | Authentication, password hashing, sessions or tokens, student and staff permissions, demo seed |
| 7 | Registrar mock API client |
| 8 | Library XML importer |
| 9 | Accounting CSV importer |
| 10 | Office and overall clearance, HOLD reasons, staff sign-off, history |
| 11 | Drop folder, logs, archive, and a daily HOLD summary only if required |
| 12 | Nager.Date and working-day deadlines |
| 13 | Signed clearance token, QR or short code, HMAC manifests, masking, audit log |
| 14 | CSV and JSON reports |
| 15 | Formal tests and evidence |
| 16 | README, guides, architecture, API docs, user manual, defense notes |

## Instructor questions

These stay open. They do not block this baseline. They do block final schema columns, invented file formats, and any feature marked confirm.

1. May this individual project use Supabase PostgreSQL instead of the brief's SQLite? If not, SQLite will be used with the same Flask design.
2. Please share the Registrar mock API base URL, auth method, endpoints, and a sample JSON payload.
3. Please share sample Library XML, Accounting CSV, and the HMAC manifest format (how the signature is computed, which bytes are signed, and how replay is detected).
4. Which offices must sign off for an individual project: Library and Accounting only, or Registrar as well? Is Student Affairs fully excluded?
5. Is a daily HOLD summary required for the individual scope, or only for the group scope?
6. What date is the working-day deadline attached to (clearance window, import SLA, or another rule)?
7. Is a signed QR verification slip an acceptable emerging-technology component?
8. How should the 30-rater evaluation be recorded (form, rubric, required screenshots)?
9. Are seeded demo accounts acceptable given there is no admin role? Planned local accounts: student `user@gmail.com` and Library staff `staff@gmail.com`. Passwords stay in `.env` and are stored only as hashes.

## Completion record

- Required, optional, and excluded lists are recorded in this file.
- Supabase versus SQLite remains an open instructor question.
- The QR slip is the default emerging-technology choice.
- Demo logins are `user@gmail.com` / `user123` (student) and `staff@gmail.com` / `staff123` (Library staff), to be seeded from `.env` as hashes in Phase 6.
- No application code has been written in Phase 1.
