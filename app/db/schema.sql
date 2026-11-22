CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'staff')),
    office TEXT NULL CHECK (office IN ('library', 'accounting')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (role = 'student' AND office IS NULL)
        OR (role = 'staff' AND office IS NOT NULL)
    )
);

CREATE UNIQUE INDEX ux_users_email_lower ON users (lower(email));

CREATE TABLE students (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_number TEXT NOT NULL UNIQUE,
    user_id BIGINT NULL UNIQUE REFERENCES users (id) ON DELETE SET NULL,
    display_name TEXT NOT NULL,
    registrar_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at TIMESTAMPTZ NULL
);

CREATE TABLE import_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('registrar_api', 'library_xml', 'accounting_csv')),
    filename TEXT NULL,
    manifest_id TEXT NULL,
    file_sha256 TEXT NULL,
    status TEXT NOT NULL CHECK (status IN ('accepted', 'rejected')),
    rows_accepted INTEGER NOT NULL DEFAULT 0 CHECK (rows_accepted >= 0),
    rows_rejected INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_import_logs_manifest_accepted
    ON import_logs (manifest_id)
    WHERE status = 'accepted' AND manifest_id IS NOT NULL;

CREATE TABLE rejected_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_log_id BIGINT NOT NULL REFERENCES import_logs (id),
    student_number TEXT NULL,
    row_number INTEGER NULL,
    reason TEXT NOT NULL,
    raw_row TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE library_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students (id),
    import_log_id BIGINT NOT NULL REFERENCES import_logs (id),
    title TEXT NOT NULL DEFAULT '',
    is_unreturned BOOLEAN NOT NULL,
    fine_cents BIGINT NOT NULL DEFAULT 0 CHECK (fine_cents >= 0),
    is_blocking BOOLEAN NOT NULL,
    source_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (is_blocking = FALSE AND is_unreturned = FALSE AND fine_cents = 0)
        OR (is_blocking = TRUE AND (is_unreturned = TRUE OR fine_cents > 0))
    )
);

CREATE INDEX ix_library_records_student_id ON library_records (student_id);

CREATE TABLE accounting_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students (id),
    import_log_id BIGINT NOT NULL REFERENCES import_logs (id),
    description TEXT NOT NULL DEFAULT '',
    balance_cents BIGINT NOT NULL CHECK (balance_cents > 0),
    is_blocking BOOLEAN NOT NULL,
    source_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (is_blocking = TRUE)
);

CREATE INDEX ix_accounting_records_student_id ON accounting_records (student_id);

CREATE TABLE office_clearance (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students (id),
    office TEXT NOT NULL CHECK (office IN ('library', 'accounting')),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'HOLD', 'CLEARED')),
    hold_reason TEXT NULL,
    signed_off_by BIGINT NULL REFERENCES users (id),
    signed_off_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (student_id, office),
    CHECK (
        (
            status = 'HOLD'
            AND hold_reason IS NOT NULL
            AND btrim(hold_reason) <> ''
        )
        OR (
            status = 'PENDING'
            AND signed_off_by IS NULL
            AND signed_off_at IS NULL
            AND hold_reason IS NULL
        )
        OR (
            status = 'CLEARED'
            AND signed_off_by IS NOT NULL
            AND signed_off_at IS NOT NULL
            AND hold_reason IS NULL
        )
    )
);

CREATE TABLE clearance (
    student_id BIGINT PRIMARY KEY REFERENCES students (id),
    overall_status TEXT NOT NULL CHECK (overall_status IN ('PENDING', 'HOLD', 'CLEARED')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clearance_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students (id),
    office TEXT NULL CHECK (office IN ('library', 'accounting')),
    action TEXT NOT NULL CHECK (action IN ('hold', 'signoff', 'import', 'slip_issued')),
    reason TEXT NOT NULL DEFAULT '',
    actor_user_id BIGINT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_clearance_events_student_id ON clearance_events (student_id);

CREATE TABLE audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id BIGINT NULL REFERENCES users (id),
    action TEXT NOT NULL,
    student_id BIGINT NULL REFERENCES students (id),
    office TEXT NULL CHECK (office IN ('library', 'accounting')),
    detail TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_audit_logs_student_id ON audit_logs (student_id);

CREATE TABLE clearance_tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id BIGINT NOT NULL REFERENCES students (id),
    token_hash TEXT NOT NULL UNIQUE,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL
);

CREATE TABLE public_holidays (
    holiday_date DATE PRIMARY KEY,
    local_name TEXT NOT NULL,
    name TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE holiday_fetch_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    calendar_year INTEGER NOT NULL CHECK (calendar_year >= 2000),
    status TEXT NOT NULL CHECK (status IN ('accepted', 'failed')),
    message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_holiday_fetch_logs_calendar_year ON holiday_fetch_logs (calendar_year, created_at DESC);
