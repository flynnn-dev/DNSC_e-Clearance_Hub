# DNSC e-Clearance Hub

One site where a student sees Library and Accounting clearance, and a staff member of one office can hold or sign off that office. The Hub does not replace the Registrar, the Library, or Accounting. It reads their exports.

Phases 1 through 16 are in the project. The short notes for each phase are in `docs/`.

## Run it on this computer

1. Install Python 3 and Node.js.
2. Follow `docs/installation.md`.
3. Open http://127.0.0.1:5000.

The two demo logins are the emails and passwords in `.env`. They are not written in this file.

## What a student can do

Sign in, read the linked clearance, and issue a signed slip when Library and Accounting are both cleared. The slip QR opens a public check that shows a masked student number.

## What staff can do

Sign in, see only their own office, place a hold, sign off when nothing is blocking, and download a CSV or JSON report. The report masks student numbers.

## Guides

| Guide | File |
| --- | --- |
| Install and start | `docs/installation.md` |
| How the parts fit | `docs/architecture.md` |
| Hub API | `docs/api.md` |
| Student and staff steps | `docs/user-manual.md` |
| Short defense notes | `docs/defense-notes.md` |
| Postman collection | `postman/DNSC-e-Clearance-Hub.postman_collection.json` |
