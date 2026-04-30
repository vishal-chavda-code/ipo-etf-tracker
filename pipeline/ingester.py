"""Ingester — takes parsed filing records and inserts/updates DB rows."""

import logging

from config import (
    IPO_INITIAL_FORMS,
    ETF_INITIAL_FORMS,
    ETF_PROSPECTUS_FORMS,
    LLM_ENRICH_N1A,
)
from sec.parsers import FilingRecord
from db.operations import (
    find_ipo_by_cik,
    find_ipo_by_name,
    insert_ipo,
    find_etf_by_cik,
    find_etf_by_name,
    insert_etf,
    update_etf,
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
        "skipped_no_initial_reg": 0,
    }

    for record in records:
        # Skip if we've already seen this exact filing
        if record.accession_number and event_exists(record.accession_number):
            summary["skipped_duplicates"] += 1
            continue

        entity_id = _ensure_entity_exists(record, summary)
        if entity_id is None:
            # _ensure_entity_exists already updated the appropriate counter
            continue

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

        # Re-run LLM enrichment on every prospectus-bearing ETF filing so that
        # amendments (N-1A/A, 485BPOS, 497, …) refresh fields like expense_ratio
        # and portfolio_manager when the underlying prospectus changes.
        if (
            LLM_ENRICH_N1A
            and record.entity_type == "ETF"
            and record.form_type in ETF_PROSPECTUS_FORMS
        ):
            _enrich_etf_from_filing(entity_id, record)

    logger.info("Ingestion summary: %s", summary)
    return summary


def _ensure_entity_exists(record: FilingRecord, summary: dict) -> int | None:
    """
    Ensure an entity (IPO or ETF) exists in the DB.

    If the entity is already tracked, return its ID.
    If not, only create a new row when the form_type is an initial
    registration form (S-1/F-1 for IPOs, N-1A for ETFs).  Otherwise
    return None so the caller skips the filing.

    Returns the entity's row ID, or None.
    """
    if record.entity_type == "IPO":
        return _ensure_ipo_exists(record, summary)
    elif record.entity_type == "ETF":
        return _ensure_etf_exists(record, summary)
    return None


def _ensure_ipo_exists(record: FilingRecord, summary: dict) -> int | None:
    """Find or create an IPO entity. Returns the row ID, or None if skipped."""
    # Try to find by CIK first (most reliable)
    existing = find_ipo_by_cik(record.cik) if record.cik else None

    # Fallback: find by entity name
    if existing is None:
        existing = find_ipo_by_name(record.entity_name)

    if existing:
        return existing["id"]

    # Only create a new entity for initial registration forms
    if record.form_type not in IPO_INITIAL_FORMS:
        logger.debug(
            "Skipping non-initial IPO form %s for %s (CIK=%s)",
            record.form_type, record.entity_name, record.cik,
        )
        summary["skipped_no_initial_reg"] += 1
        return None

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


def _ensure_etf_exists(record: FilingRecord, summary: dict) -> int | None:
    """Find or create an ETF entity. Returns the row ID, or None if skipped."""
    existing = find_etf_by_cik(record.cik) if record.cik else None

    if existing is None:
        existing = find_etf_by_name(record.entity_name)

    if existing:
        return existing["id"]

    # Only create a new entity for initial registration forms
    if record.form_type not in ETF_INITIAL_FORMS:
        logger.debug(
            "Skipping non-initial ETF form %s for %s (CIK=%s)",
            record.form_type, record.entity_name, record.cik,
        )
        summary["skipped_no_initial_reg"] += 1
        return None

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


def _enrich_etf_from_filing(etf_id: int, record: FilingRecord) -> None:
    """Run LLM enrichment for an ETF using the given prospectus-bearing filing.

    Called for every N-1A / N-1A/A / 485BPOS / 497 / 497K filing — both on the
    initial registration and on subsequent amendments. Merge semantics: only
    fields the LLM actually populates from the new filing overwrite existing
    values, so a field omitted from a sticker (e.g. 497 doesn't repeat the
    portfolio manager) doesn't wipe a value extracted from an earlier N-1A.

    Imported lazily so the openai dependency is only loaded when actually used,
    and so an enrichment failure can never block ingestion of the filing event.
    """
    try:
        from pipeline.enricher import enrich_n1a
    except Exception as e:
        logger.warning("Enricher import failed; skipping enrichment: %s", e)
        return

    try:
        fields = enrich_n1a(record.cik, record.accession_number)
    except Exception as e:
        logger.warning("Enrichment crashed for ETF id=%d (%s): %s", etf_id, record.entity_name, e)
        return

    if not fields:
        logger.info("Enrichment yielded no fields for ETF id=%d (%s)", etf_id, record.entity_name)
        return

    # Drop None values so a sparse later filing can't clobber a populated field.
    # Always keep enriched_at — it records that we ran the LLM against this filing.
    enriched_at = fields.get("enriched_at")
    updates = {k: v for k, v in fields.items() if v is not None and k != "enriched_at"}
    if enriched_at:
        updates["enriched_at"] = enriched_at

    if not updates:
        return

    update_etf(etf_id, updates)
