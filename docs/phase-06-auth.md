# DNSC e-Clearance Hub — Phase 6 Authentication

Status: student and staff can sign in and sign out. Clearance records are still empty.

Demo accounts are created by `python -m scripts.seed_users`. The command reads the emails and passwords from `.env` and stores PBKDF2 hashes. A signed-in student can open `/student` only. A signed-in staff member can open `/staff` only. The other address returns "You cannot open this page."

The session cookie is HttpOnly and SameSite is Lax. It stores the user id and role. Passwords and the database URL stay on the server. Login and logout require the CSRF token printed in the form.
