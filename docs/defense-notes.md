# Defense notes

## What the Hub changes

A student used to walk from the Library to Accounting with a paper slip. The Hub keeps one clearance. Registrar supplies the identity. Library and Accounting still decide their own hold or sign-off. The Hub only reads their files.

## Why a slip can fail after it was signed

The signature proves the Hub issued the slip. It does not freeze the clearance. The public check reads the current status. A hold after issue revokes the slip, so a copied QR cannot be used as proof once the student is on hold.

## How the imports are trusted

The Accounting manifest is HMAC-SHA256 over the JSON with `signature` removed, keys sorted, and no extra spaces. The file bytes must match `sha256`. An accepted nonce cannot be imported again. A bad signature is rejected before any row is read. Rows that fail validation are logged and skipped. The good rows are kept.

## How accounts are limited

Passwords are stored as PBKDF2 hashes. The session cookie is HttpOnly. Staff and student checks run on the server for every API call. A student cannot call a staff URL by typing it. SQL values are parameters, not pasted into the query text. Reports and the public slip page show a masked student number.

## Clearance deadline

The student overview shows a deadline counted in working days from `CLEARANCE_ANCHOR_DATE` for `CLEARANCE_WORKING_DAYS`. The count skips weekends and Philippine public holidays. The date does not change PENDING, HOLD, or CLEARED. If that year's holiday list was never saved, the page says the deadline is unavailable. It does not assume there were no holidays.

## What is still open

These were left as the instructor asked, and the Hub does not invent an answer:

- A daily hold summary was not built. That item was for the group scope unless the instructor requires it here.
- There is one staff demo account. A second account, for Accounting, is added when both offices need a login at the same time.
