# DNSC e-Clearance Hub — Phase 12 Working days

Status: the student clearance API returns this deadline, and the student overview shows it. The count skips Saturdays, Sundays, and public holidays from Nager.Date. The date does not change an office status. `CLEARANCE_ANCHOR_DATE` and `CLEARANCE_WORKING_DAYS` set the count.

Nager.Date is requested at `https://date.nager.at/api/v3/PublicHolidays/{year}/PH`. A successful list is saved in `public_holidays`. If a later request fails and that year was saved before, the count uses the saved list and writes a failed row in `holiday_fetch_logs`. If the request fails and that year was never saved, the count stops. It does not pretend there are no holidays.

```powershell
python -m app.db.migrate
python -m scripts.working_days 2026-11-20 5
```

The first date is the start. The number is how many working days to add after that start. The start day itself is not counted. `2026-11-20` is a Friday, so five working days later is `2026-11-27` unless a public holiday falls in between.
