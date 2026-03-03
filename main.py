"""Entry point — runs the daily batch pipeline for IPO/ETF tracking."""

import argparse
import logging
import sys
from datetime import date, timedelta

from config import DB_PATH
from db.operations import init_db, get_unread_notifications
from sec.client import EdgarClient
from sec.parsers import parse_daily_index
from pipeline.ingester import ingest_filings
from pipeline.lifecycle import advance_lifecycle
from pipeline.notifier import check_and_notify_launches

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run_daily(target_date: date) -> None:
    """Run the full pipeline for a single day."""
    logger.info("=" * 60)
    logger.info("Processing filings for %s", target_date.isoformat())
    logger.info("=" * 60)

    client = EdgarClient()

    # Step 1: Fetch daily index
    logger.info("Step 1/4: Fetching EDGAR daily index...")
    raw_index = client.fetch_daily_index(target_date)
    if not raw_index:
        logger.info("No index data for %s — skipping.", target_date.isoformat())
        return

    # Step 2: Parse for IPO/ETF filings
    logger.info("Step 2/4: Parsing filings...")
    records = parse_daily_index(raw_index)
    if not records:
        logger.info("No relevant IPO/ETF filings found for %s.", target_date.isoformat())
        return

    logger.info("Found %d relevant filings.", len(records))

    # Step 3: Ingest into database
    logger.info("Step 3/4: Ingesting into database...")
    ingest_summary = ingest_filings(records)
    logger.info("Ingestion: %s", ingest_summary)

    # Step 4: Advance lifecycle + check for launches
    logger.info("Step 4/4: Advancing lifecycle & checking launches...")
    lifecycle_summary = advance_lifecycle()
    logger.info("Lifecycle: %s", lifecycle_summary)

    notifier_summary = check_and_notify_launches()
    logger.info("Notifier: %s", notifier_summary)

    # Print unread notifications
    unread = get_unread_notifications()
    if unread:
        logger.info("--- UNREAD NOTIFICATIONS ---")
        for n in unread:
            logger.info("  [%s] %s", n["entity_type"], n["message"])


def run_backfill(days: int) -> None:
    """Run the pipeline for the last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    logger.info(
        "Backfilling %d days: %s → %s",
        days,
        start_date.isoformat(),
        end_date.isoformat(),
    )
    current = start_date
    while current <= end_date:
        run_daily(current)
        current += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(
        description="IPO & ETF Launch Tracker — SEC EDGAR pipeline"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize the database (create tables)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the daily pipeline for today",
    )
    parser.add_argument(
        "--backfill",
        type=int,
        metavar="DAYS",
        help="Backfill the last N days of filings",
    )
    parser.add_argument(
        "--date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Run the pipeline for a specific date",
    )

    args = parser.parse_args()

    if not any([args.init, args.run, args.backfill, args.date]):
        parser.print_help()
        sys.exit(1)

    if args.init:
        logger.info("Initializing database at %s", DB_PATH)
        init_db()
        logger.info("Database ready.")

    if args.backfill:
        init_db()  # Ensure tables exist
        run_backfill(args.backfill)
    elif args.date:
        init_db()
        target = date.fromisoformat(args.date)
        run_daily(target)
    elif args.run:
        init_db()
        run_daily(date.today())

    logger.info("Done.")


if __name__ == "__main__":
    main()
