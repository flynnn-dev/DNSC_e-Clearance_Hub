# DNSC e-Clearance Hub — Phase 15 Tests

Status: 44 tests passed in 7 minutes 48 seconds.

```powershell
python -m pytest -q
```

The suite covers sign-in, the wrong role, SQL injection on the login and on a student number, tampered manifests, an expired slip, a revoked slip, and masked office reports. The Postman collection is `postman/DNSC-e-Clearance-Hub.postman_collection.json`.
