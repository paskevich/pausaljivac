-- Entrepreneur's own fixed info, editable via Settings page (no code edits needed)
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS invoice_sequences (
    year     INTEGER PRIMARY KEY,
    next_seq INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clients (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    country        TEXT,
    address        TEXT,
    email          TEXT,
    contact_person TEXT,
    default_currency TEXT DEFAULT 'EUR',
    notes          TEXT,
    is_active      BOOLEAN NOT NULL DEFAULT 1,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    id         INTEGER PRIMARY KEY,
    rate_date  DATE NOT NULL,
    currency   TEXT NOT NULL CHECK(currency IN ('EUR','USD')),
    rsd_rate   NUMERIC NOT NULL,
    source     TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','nbs_fetch','nbs_import')),
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rate_date, currency)
);

CREATE TABLE IF NOT EXISTS invoices (
    id                   INTEGER PRIMARY KEY,
    invoice_number       TEXT UNIQUE NOT NULL,
    client_id            INTEGER NOT NULL REFERENCES clients(id),
    issue_date           DATE NOT NULL,
    service_date         DATE,
    due_date              DATE,
    currency             TEXT NOT NULL CHECK(currency IN ('EUR','USD')),
    amount               NUMERIC NOT NULL,
    description           TEXT NOT NULL,
    exchange_rate         NUMERIC,
    exchange_rate_date    DATE,
    exchange_rate_source  TEXT,
    amount_rsd            NUMERIC,
    status                TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','issued','paid','cancelled')),
    pdf_path              TEXT,
    notes                 TEXT,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices(issue_date);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id                 INTEGER PRIMARY KEY,
    category           TEXT NOT NULL CHECK(category IN ('resenje','contract','other','invoice','bank_report')),
    client_id          INTEGER REFERENCES clients(id),
    invoice_id         INTEGER REFERENCES invoices(id),
    resenje_id         INTEGER REFERENCES tax_resenja(id),
    period_year        INTEGER,
    period_month       INTEGER,
    title              TEXT NOT NULL,
    file_path          TEXT NOT NULL,
    original_filename  TEXT,
    mime_type          TEXT,
    notes              TEXT,
    uploaded_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_client ON documents(client_id);
CREATE INDEX IF NOT EXISTS idx_documents_period ON documents(period_year, period_month);
CREATE INDEX IF NOT EXISTS idx_documents_resenje ON documents(resenje_id);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, tag_id)
);

CREATE TABLE IF NOT EXISTS tax_resenja (
    id                          INTEGER PRIMARY KEY,
    resenje_number              TEXT,
    valid_from                  DATE NOT NULL,
    valid_to                    DATE,
    pausal_tax_amount           NUMERIC NOT NULL,
    pio_contribution            NUMERIC NOT NULL,
    health_contribution         NUMERIC NOT NULL,
    unemployment_contribution   NUMERIC NOT NULL DEFAULT 0,
    notes                       TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tax_payments (
    id                          INTEGER PRIMARY KEY,
    period_year                 INTEGER NOT NULL,
    period_month                INTEGER NOT NULL,
    due_date                    DATE NOT NULL,
    resenje_id                  INTEGER REFERENCES tax_resenja(id),
    pausal_tax_amount           NUMERIC,
    pio_contribution            NUMERIC,
    health_contribution         NUMERIC,
    unemployment_contribution   NUMERIC,
    amount_due                  NUMERIC NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'unpaid' CHECK(status IN ('unpaid','paid')),
    paid_date                   DATE,
    payment_document_id         INTEGER REFERENCES documents(id),
    notes                       TEXT,
    UNIQUE(period_year, period_month)
);
