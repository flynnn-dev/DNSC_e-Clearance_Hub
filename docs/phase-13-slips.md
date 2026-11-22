# DNSC e-Clearance Hub — Phase 13 Signed slips

Status: a student can issue a signed clearance slip when Library and Accounting are both cleared. The slip lasts 14 calendar days. The QR code opens a public page. That page checks the signature, the expiry, and the current clearance. It shows a masked student number, such as `2023-***35`. It does not show the name, a fine, a book, or a balance.

A later hold revokes an open slip. The public page then says the slip was revoked. A valid signature does not keep the student cleared.

Open `/student` and use Issue slip when the overall status is cleared. The QR code and the link open `/verify/<token>`. That page can be opened without signing in.

An Accounting manifest is checked with HMAC-SHA256 before any row is read. The signed bytes are the manifest JSON without `signature`, keys sorted, separators comma and colon. `HMAC_SECRET` in `.env` is the key. A bad signature or a changed file is rejected. A repeated nonce is still rejected.

The 14-day slip lifetime is not the working-day deadline. That count is still not attached to a clearance.
