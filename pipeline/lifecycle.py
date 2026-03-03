"""Lifecycle manager — advances entity status based on new filing events."""

import logging

from config import FORM_TO_STATUS, STATUS_ORDER, STATUS_LAUNCHED
from db.operations import (
    get_connection,
    update_ipo,
    update_etf,
)

logger = logging.getLogger(__name__)


def advance_lifecycle() -> dict:
    """
    Scan all entities that aren't LAUNCHED/COMPLETED and advance their status
    based on the latest filing event.

    Logic:
      - For each entity in stock_ipos / etf_launches that is not LAUNCHED:
        - Look at all filing_events for that entity
        - Determine the highest-status filing event
        - If that status is higher than the current entity status, advance it

    Returns a summary of status changes.
    """
    summary = {"ipos_advanced": 0, "etfs_advanced": 0}

    conn = get_connection()
    try:
        # Advance IPOs
        ipos = conn.execute(
            "SELECT id, status FROM stock_ipos WHERE status NOT IN ('LAUNCHED', 'COMPLETED')"
        ).fetchall()

        for ipo in ipos:
            ipo_id = ipo["id"]
            current_status = ipo["status"]

            new_status = _get_highest_event_status(conn, "IPO", ipo_id)
            if new_status and _is_advancement(current_status, new_status):
                update_ipo(ipo_id, {"status": new_status})
                logger.info(
                    "IPO id=%d advanced: %s → %s", ipo_id, current_status, new_status
                )
                summary["ipos_advanced"] += 1

        # Advance ETFs
        etfs = conn.execute(
            "SELECT id, status FROM etf_launches WHERE status NOT IN ('LAUNCHED', 'COMPLETED')"
        ).fetchall()

        for etf in etfs:
            etf_id = etf["id"]
            current_status = etf["status"]

            new_status = _get_highest_event_status(conn, "ETF", etf_id)
            if new_status and _is_advancement(current_status, new_status):
                update_etf(etf_id, {"status": new_status})
                logger.info(
                    "ETF id=%d advanced: %s → %s", etf_id, current_status, new_status
                )
                summary["etfs_advanced"] += 1

    finally:
        conn.close()

    logger.info("Lifecycle summary: %s", summary)
    return summary


def _get_highest_event_status(conn, entity_type: str, entity_id: int) -> str | None:
    """
    Look at all filing events for an entity, map each to a lifecycle status,
    and return the highest one.
    """
    events = conn.execute(
        "SELECT form_type FROM filing_events WHERE entity_type = ? AND entity_id = ?",
        (entity_type, entity_id),
    ).fetchall()

    if not events:
        return None

    highest_status = None
    highest_order = -1

    for event in events:
        form_type = event["form_type"]
        status = FORM_TO_STATUS.get(form_type)
        if status and STATUS_ORDER.get(status, -1) > highest_order:
            highest_status = status
            highest_order = STATUS_ORDER[status]

    return highest_status


def _is_advancement(current_status: str, new_status: str) -> bool:
    """Check if new_status is a forward advancement from current_status."""
    current_order = STATUS_ORDER.get(current_status, -1)
    new_order = STATUS_ORDER.get(new_status, -1)
    return new_order > current_order
