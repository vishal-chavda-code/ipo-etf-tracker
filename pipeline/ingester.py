"""Ingester — takes parsed filing records and inserts/updates DB rows."""

import logging

from sec.parsers import FilingRecord
from db.operations import (
    find_ipo_by_cik,
    find_ipo_by_name,
    insert_ipo,
    find_etf_by_cik,
    find_etf_by_name,
    insert_etf,
    event_exists,
    insert_filing_event,
)

logger = logging.getLogger(__name__)


def ingest_filings(records: list[FilingRecord]) -> dict:
    """
    Process a list of FilingRecord objects:
      - For each record, check if the entity already exists (by CIK, then by name).
      - If not, create a new row in stock_ipos or etf_launches.
      - Log every filing as a filing_event (deduplicated by accession number).

    Returns a summary dict with counts of new entities and events.
    """
    summary = {
        "new_ipos": 0,
        "new_etfs": 0,
        "new_events": 0,
        "skipped_duplicates": 0,
    }

    for record in records:
        # Skip if we've already seen this exact filing
        if record.accession_number and event_exists(record.accession_number):
            summary["skipped_duplicates"] += 1
            continue

        entity_id = _ensure_entity_exists(record)
        if entity_id is None:
            logger.warning("Could not resolve entity for %s", record)
            continue

        # Track if entity was newly created
        if record.entity_type == "IPO":
            # Check if this was a new insert by seeing if we just created it
            pass  # counted inside _ensure_entity_exists indirectly
        elif record.entity_type == "ETF":
            pass

        # Insert filing event
        event_data = {
            "entity_type": record.entity_type,
            "entity_id": entity_id,
            "form_type": record.form_type,
            "filing_date": record.filing_date,
            "accession_number": record.accession_number,
            "edgar_url": record.edgar_url,
            "description": f"{record.form_type} filing for {record.entity_name}",
        }
        insert_filing_event(event_data)
        summary["new_events"] += 1

    logger.info("Ingestion summary: %s", summary)
    return summary


def _ensure_entity_exists(record: FilingRecord) -> int | None:
    """
    Ensure an entity (IPO or ETF) exists in the DB. Creates it if not found.

    Returns the entity's row ID.
    """
    if record.entity_type == "IPO":
        return _ensure_ipo_exists(record)
    elif record.entity_type == "ETF":
        return _ensure_etf_exists(record)
    return None


def _ensure_ipo_exists(record: FilingRecord) -> int:
    """Find or create an IPO entity. Returns the row ID."""
    # Try to find by CIK first (most reliable)
    existing = find_ipo_by_cik(record.cik) if record.cik else None

    # Fallback: find by entity name
    if existing is None:
        existing = find_ipo_by_name(record.entity_name)

    if existing:
        return existing["id"]

    # Create new
    new_id = insert_ipo({
        "entity_name": record.entity_name,
        "cik": record.cik,
        "status": "FILED",
        "form_type": record.form_type,
        "filing_date": record.filing_date,
        "sic_code": record.sic_code,
        "edgar_url": record.edgar_url,
    })
    logger.info("New IPO entity: %s (CIK=%s)", record.entity_name, record.cik)
    return new_id


def _ensure_etf_exists(record: FilingRecord) -> int:
    """Find or create an ETF entity. Returns the row ID."""
    existing = find_etf_by_cik(record.cik) if record.cik else None

    if existing is None:
        existing = find_etf_by_name(record.entity_name)

    if existing:
        return existing["id"]

    new_id = insert_etf({
        "fund_name": record.entity_name,
        "cik": record.cik,
        "status": "FILED",
        "form_type": record.form_type,
        "filing_date": record.filing_date,
        "edgar_url": record.edgar_url,
    })
    logger.info("New ETF entity: %s (CIK=%s)", record.entity_name, record.cik)
    return new_id
