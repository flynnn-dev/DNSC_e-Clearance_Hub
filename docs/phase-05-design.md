# DNSC e-Clearance Hub — Phase 5 Design System

Status: layouts are in the running app. Sign-in, live clearance data, and staff actions are not connected.

## Screens

- `/` and `/login` — sign-in form. A submitted password is not stored. The page says sign-in is not connected yet.
- `/student` — student shell: overall, library, and accounting cards, profile, history table, and slip area. Values stay empty.
- `/staff` — staff shell: student table, office counts, and a hold dialog that can be opened and closed. It does not save a hold.

## Shared pieces

Colors are navy, white, and slate. Buttons, fields, cards, badges, and tables use the classes in `assets/css/input.css`. The sidebar is a drawer below 768 pixels and a fixed column on wider screens. Tables scroll inside their card instead of widening the page.

Phase 6 replaces the login notice with a real session.
