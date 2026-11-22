# DNSC e-Clearance Hub — Phase 9 Accounting CSV

Status: an Accounting balance export can be imported. A zero balance is not stored. Staff sign-off is still a later phase. The manifest signature is still unchecked.

The starter file is `samples/accounting/accounting_balances_2026-11-20.csv`. The columns are `StudentNo`, `Name`, `Term`, `Assessed`, `Paid`, `Balance`, and `LastPaymentDate`. Amounts may contain commas, such as `1,500.00`. They are stored in centavos. `Balance` must equal `Assessed` minus `Paid`.

A balance above zero is a blocking Accounting row. The description is the term, `1S 2026-2027`, and the hold reason looks like `Balance 1,500.00 for 1S 2026-2027`. That office becomes HOLD, and the overall clearance becomes HOLD if it was not already. A balance of zero deletes that student's Accounting row and returns Accounting to PENDING, unless a staff hold or a sign-off is still in place. A Library hold is left alone, so the overall status stays HOLD when Library is still holding the student.

The sibling manifest `accounting_balances_2026-11-20.csv.manifest.json` is checked for the file name, the SHA-256 of the CSV bytes, the record count, and `source`. The starter hash matches. The `signature` and `nonce` are stored for Phase 13. This phase does not decide whether that signature is valid, because the signed-byte rule is not in the file.

These starter rows are rejected:

- `2023-55555` is not in the Registrar masterlist
- the second `2024-45481` has `Paid` of `abc` and `Balance` of `x`

The first `2024-45481` row is a zero balance and is kept.

Run:

```powershell
python -m scripts.import_accounting samples/accounting/accounting_balances_2026-11-20.csv
```
