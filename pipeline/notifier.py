"""Notifier — detects LAUNCHED entities and creates notifications + active_securities rows."""

import logging
from datetime import datetime

from config import STATUS_EFFECTIVE, STATUS_LAUNCHED, STATUS_COMPLETED
from db.operations import (
    get_connection,
    update_ipo,
    update_etf,
    insert_active_security,
    insert_notification,
)

logger = logging.getLogger(__name__)


def check_and_notify_launches() -> dict:
    """
    Find entities that have reached EFFECTIVE status and promote them:
      1. Mark as LAUNCHED
      2. Insert into active_securities
      3. Insert a notification

    Note: In a real production system, LAUNCHED would be detected by an actual
    exchange listing or trading data. For now, we treat EFFECTIVE as the
    trigger to move to LAUNCHED, since EFFECT / 8-A12B / 485BPOS filings
    indicate the SEC has cleared the security for trading.

    Returns a summary dict.
    """
    summary = {"ipos_launched": 0, "etfs_launched": 0, "notifications_created": 0}

    conn = get_connection()
    try:
        # --- IPOs that reached EFFECTIVE ---
        effective_ipos = conn.execute(
            "SELECT * FROM stock_ipos WHERE status = ?", (STATUS_EFFECTIVE,)
        ).fetchall()

        for ipo in effective_ipos:
            ipo_dict = dict(ipo)
            now = datetime.utcnow().isoformat()

            # Mark as LAUNCHED
            update_ipo(ipo_dict["id"], {
                "status": STATUS_LAUNCHED,
                "launch_date": now,
            })

            # Insert into active_securities
            insert_active_security({
                "entity_type": "IPO",
                "entity_name": ipo_dict["entity_name"],
                "ticker": ipo_dict.get("ticker"),
                "launch_date": now,
                "source_id": ipo_dict["id"],
            })

            # Create notification
            ticker_str = f" ({ipo_dict['ticker']})" if ipo_dict.get("ticker") else ""
            insert_notification({
                "entity_type": "IPO",
                "entity_name": ipo_dict["entity_name"],
                "ticker": ipo_dict.get("ticker"),
                "message": (
                    f"🚀 IPO LAUNCHED: {ipo_dict['entity_name']}{ticker_str} "
                    f"has been declared effective by the SEC and is ready for trading."
                ),
            })

            summary["ipos_launched"] += 1
            summary["notifications_created"] += 1
            logger.info(
                "IPO LAUNCHED: %s%s",
                ipo_dict["entity_name"],
                ticker_str,
            )

        # --- ETFs that reached EFFECTIVE ---
        effective_etfs = conn.execute(
            "SELECT * FROM etf_launches WHERE status = ?", (STATUS_EFFECTIVE,)
        ).fetchall()

        for etf in effective_etfs:
            etf_dict = dict(etf)
            now = datetime.utcnow().isoformat()

            update_etf(etf_dict["id"], {
                "status": STATUS_LAUNCHED,
                "launch_date": now,
            })

            insert_active_security({
                "entity_type": "ETF",
                "entity_name": etf_dict["fund_name"],
                "ticker": etf_dict.get("ticker"),
                "launch_date": now,
                "source_id": etf_dict["id"],
            })

            ticker_str = f" ({etf_dict['ticker']})" if etf_dict.get("ticker") else ""
            insert_notification({
                "entity_type": "ETF",
                "entity_name": etf_dict["fund_name"],
                "ticker": etf_dict.get("ticker"),
                "message": (
                    f"🚀 ETF LAUNCHED: {etf_dict['fund_name']}{ticker_str} "
                    f"has been declared effective and is ready for trading."
                ),
            })

            summary["etfs_launched"] += 1
            summary["notifications_created"] += 1
            logger.info(
                "ETF LAUNCHED: %s%s",
                etf_dict["fund_name"],
                ticker_str,
            )

    finally:
        conn.close()

    logger.info("Notifier summary: %s", summary)
    return summary
