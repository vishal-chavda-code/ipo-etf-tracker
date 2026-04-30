"""Database CRUD operations for the IPO/ETF tracker."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from config import DB_PATH
from db.models import SCHEMA_SQL

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist, then run lightweight column migrations."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        _migrate_etf_enrichment_columns(conn)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


# Columns added to etf_launches after the original schema shipped.
# SQLite's CREATE TABLE IF NOT EXISTS won't add columns to a pre-existing table,
# so we ALTER TABLE for any that are missing.
_ETF_ENRICHMENT_COLUMNS = [
    ("investment_theme",   "TEXT"),
    ("expense_ratio",      "REAL"),
    ("portfolio_manager",  "TEXT"),
    ("benchmark_index",    "TEXT"),
    ("asset_class",        "TEXT"),
    ("fund_type",          "TEXT"),
    ("principal_strategy", "TEXT"),
    ("enriched_at",        "TEXT"),
]


def _migrate_etf_enrichment_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(etf_launches)")}
    for col, ddl_type in _ETF_ENRICHMENT_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE etf_launches ADD COLUMN {col} {ddl_type}")
            logger.info("Added column etf_launches.%s", col)


# ---------------------------------------------------------------------------
# Stock IPOs
# ---------------------------------------------------------------------------

def find_ipo_by_cik(cik: str) -> dict | None:
    """Find an existing IPO entry by CIK."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM stock_ipos WHERE cik = ?", (cik,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def find_ipo_by_name(entity_name: str) -> dict | None:
    """Find an existing IPO entry by entity name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM stock_ipos WHERE LOWER(entity_name) = LOWER(?)",
            (entity_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def insert_ipo(data: dict) -> int:
    """Insert a new stock IPO row. Returns the new row id."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            """INSERT INTO stock_ipos
               (entity_name, ticker, cik, status, form_type, filing_date,
                exchange, sic_code, edgar_url, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("entity_name"),
                data.get("ticker"),
                data.get("cik"),
                data.get("status", "FILED"),
                data.get("form_type"),
                data.get("filing_date"),
                data.get("exchange"),
                data.get("sic_code"),
                data.get("edgar_url"),
                now,
                now,
            ),
        )
        conn.commit()
        logger.info("Inserted IPO: %s (id=%d)", data.get("entity_name"), cur.lastrowid)
        return cur.lastrowid
    finally:
        conn.close()


def update_ipo(ipo_id: int, updates: dict) -> None:
    """Update an existing IPO row with the given fields."""
    conn = get_connection()
    try:
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [ipo_id]
        conn.execute(
            f"UPDATE stock_ipos SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        logger.info("Updated IPO id=%d: %s", ipo_id, list(updates.keys()))
    finally:
        conn.close()


def get_ipos_by_status(status: str) -> list[dict]:
    """Get all IPOs with a given status."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM stock_ipos WHERE status = ? ORDER BY filing_date DESC",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_ipos() -> list[dict]:
    """Get all IPO rows."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM stock_ipos ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ETF Launches
# ---------------------------------------------------------------------------

def find_etf_by_cik(cik: str) -> dict | None:
    """Find an existing ETF entry by CIK."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM etf_launches WHERE cik = ?", (cik,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def find_etf_by_name(fund_name: str) -> dict | None:
    """Find an existing ETF entry by fund name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM etf_launches WHERE LOWER(fund_name) = LOWER(?)",
            (fund_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def insert_etf(data: dict) -> int:
    """Insert a new ETF launch row. Returns the new row id."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            """INSERT INTO etf_launches
               (fund_name, ticker, cik, status, form_type, filing_date,
                exchange, issuer, edgar_url, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("fund_name"),
                data.get("ticker"),
                data.get("cik"),
                data.get("status", "FILED"),
                data.get("form_type"),
                data.get("filing_date"),
                data.get("exchange"),
                data.get("issuer"),
                data.get("edgar_url"),
                now,
                now,
            ),
        )
        conn.commit()
        logger.info("Inserted ETF: %s (id=%d)", data.get("fund_name"), cur.lastrowid)
        return cur.lastrowid
    finally:
        conn.close()


def update_etf(etf_id: int, updates: dict) -> None:
    """Update an existing ETF row with the given fields."""
    conn = get_connection()
    try:
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [etf_id]
        conn.execute(
            f"UPDATE etf_launches SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        logger.info("Updated ETF id=%d: %s", etf_id, list(updates.keys()))
    finally:
        conn.close()


def get_etfs_by_status(status: str) -> list[dict]:
    """Get all ETFs with a given status."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM etf_launches WHERE status = ? ORDER BY filing_date DESC",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_etfs() -> list[dict]:
    """Get all ETF rows."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM etf_launches ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Filing Events
# ---------------------------------------------------------------------------

def event_exists(accession_number: str) -> bool:
    """Check if a filing event with this accession number already exists."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM filing_events WHERE accession_number = ?",
            (accession_number,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_filing_event(data: dict) -> int:
    """Insert a filing event row. Returns the new row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO filing_events
               (entity_type, entity_id, form_type, filing_date,
                accession_number, edgar_url, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["entity_type"],
                data["entity_id"],
                data["form_type"],
                data.get("filing_date"),
                data.get("accession_number"),
                data.get("edgar_url"),
                data.get("description"),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_events_for_entity(entity_type: str, entity_id: int) -> list[dict]:
    """Get all filing events for a given entity."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM filing_events
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY filing_date ASC""",
            (entity_type, entity_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Active Securities
# ---------------------------------------------------------------------------

def insert_active_security(data: dict) -> int:
    """Insert a row into active_securities. Returns the new row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO active_securities
               (entity_type, entity_name, ticker, launch_date, source_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["entity_type"],
                data["entity_name"],
                data.get("ticker"),
                data.get("launch_date"),
                data["source_id"],
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_active_securities() -> list[dict]:
    """Get all active (launched) securities."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM active_securities ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def insert_notification(data: dict) -> int:
    """Insert a notification row. Returns the new row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO notifications
               (entity_type, entity_name, ticker, message, is_read, created_at)
               VALUES (?, ?, ?, ?, 0, ?)""",
            (
                data["entity_type"],
                data["entity_name"],
                data.get("ticker"),
                data["message"],
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_unread_notifications() -> list[dict]:
    """Get all unread notifications."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_notification_read(notification_id: int) -> None:
    """Mark a notification as read."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ?",
            (notification_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_notifications() -> list[dict]:
    """Get all notifications."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM notifications ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
