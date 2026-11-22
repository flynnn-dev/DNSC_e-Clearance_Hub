# DNSC e-Clearance Hub — Phase 11 Drop folder

Status: one command imports every Library XML and Accounting CSV waiting in `drop/incoming`. A file stays there until the database commit finishes. It then moves to `drop/archive`. A broken file, a bad Accounting manifest, or a file that was already accepted moves to `drop/rejected`. Each run writes a log in `drop/logs`.

```powershell
python -m scripts.process_drop_folder
```

Put the export in `drop/incoming`. An Accounting CSV may sit beside `the-file.csv.manifest.json`. The folder checks the HMAC signature before it reads any row. The signed bytes are the manifest JSON without `signature`, with the keys sorted and no spaces. It then checks the file name, the SHA-256, the record count, and `source`. A file whose bytes or manifest `nonce` were already accepted is rejected. The key is `HMAC_SECRET` in `.env`.

A file that parses can still contain bad rows. Those rows are rejected, the good rows are saved, and the file is archived. The direct import commands still work on a path you choose. This command is the shared folder.

Library files imported before this phase did not store a file hash. The first drop of that same XML is treated as a new import. After that, dropping the same bytes is a replay.
