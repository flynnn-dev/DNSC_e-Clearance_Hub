# User manual

Open http://127.0.0.1:5000 and sign in with the demo account from `.env`.

## Student

The student page shows the overall status, Library, Accounting, the profile, and the history.

- **Pending** means an office has no blocking record and has not signed off.
- **Hold** means a fine, an unreturned book, a balance, or a staff hold is current. The reason is on the card.
- **Cleared** means that office signed off and nothing blocking is current.

**Issue slip** turns on only when the overall status is cleared. The page then shows a QR code and a link. Anyone who opens that link sees a masked student number and whether the slip is still cleared. A later hold makes the slip say it was revoked.

## Library or Accounting staff

The staff page lists only that office.

- **Sign off** is available when that student has no blocking record for the office.
- **Hold** asks for a reason. The reason is stored and shown to the student.
- **Download CSV** and **Download JSON** save the office list. Student numbers in the file are masked. The table on the screen keeps the full number.

A staff account cannot open the student page, and a student account cannot open the staff page.

## Importing a new office file

Put a `.xml` or `.csv` file in `drop\incoming`. An Accounting CSV needs its `.csv.manifest.json` beside it. Then run:

```powershell
python -m scripts.process_drop_folder
```

A valid file moves to `drop\archive`. A bad signature, a changed file, or a file that was already imported moves to `drop\rejected`. The run log is in `drop\logs`.
