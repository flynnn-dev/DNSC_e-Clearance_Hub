# DNSC e-Clearance Hub — Phase 14 Reports

Status: Library or Accounting staff can download a CSV or JSON report for their own office. The student numbers in that file are masked, such as `2023-***35`. The screen still shows the full number. Asking for the other office in the query string does not change the file. The office comes from the signed-in staff account.

```text
GET /api/office/reports.csv
GET /api/office/reports.json
```

A student receives 403. A visitor who is not signed in receives 401.
