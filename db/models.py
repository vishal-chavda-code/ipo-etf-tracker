"""SQLite table schemas — CREATE TABLE statements for the IPO/ETF tracker."""

SCHEMA_SQL = """
-- Stock IPO pipeline tracker
CREATE TABLE IF NOT EXISTS stock_ipos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name     TEXT    NOT NULL,
    ticker          TEXT,
    cik             TEXT,
    status          TEXT    NOT NULL DEFAULT 'FILED',
    form_type       TEXT,
    filing_date     TEXT,
    effective_date  TEXT,
    launch_date     TEXT,
    price           REAL,
    exchange        TEXT,
    sic_code        TEXT,
    edgar_url       TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ETF launch pipeline tracker
CREATE TABLE IF NOT EXISTS etf_launches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_name       TEXT    NOT NULL,
    ticker          TEXT,
    cik             TEXT,
    status          TEXT    NOT NULL DEFAULT 'FILED',
    form_type       TEXT,
    filing_date     TEXT,
    effective_date  TEXT,
    launch_date     TEXT,
    exchange        TEXT,
    issuer          TEXT,
    edgar_url       TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Audit log: every individual filing event
CREATE TABLE IF NOT EXISTS filing_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type       TEXT    NOT NULL CHECK(entity_type IN ('IPO', 'ETF')),
    entity_id         INTEGER NOT NULL,
    form_type         TEXT    NOT NULL,
    filing_date       TEXT,
    accession_number  TEXT    UNIQUE,
    edgar_url         TEXT,
    description       TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Launched entities (action table)
CREATE TABLE IF NOT EXISTS active_securities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT    NOT NULL CHECK(entity_type IN ('IPO', 'ETF')),
    entity_name     TEXT    NOT NULL,
    ticker          TEXT,
    launch_date     TEXT,
    source_id       INTEGER NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Launch notifications
CREATE TABLE IF NOT EXISTS notifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT    NOT NULL CHECK(entity_type IN ('IPO', 'ETF')),
    entity_name     TEXT    NOT NULL,
    ticker          TEXT,
    message         TEXT    NOT NULL,
    is_read         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_stock_ipos_status ON stock_ipos(status);
CREATE INDEX IF NOT EXISTS idx_stock_ipos_cik ON stock_ipos(cik);
CREATE INDEX IF NOT EXISTS idx_etf_launches_status ON etf_launches(status);
CREATE INDEX IF NOT EXISTS idx_etf_launches_cik ON etf_launches(cik);
CREATE INDEX IF NOT EXISTS idx_filing_events_entity ON filing_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_filing_events_accession ON filing_events(accession_number);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(is_read);
"""
