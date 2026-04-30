"""Live end-to-end smoke test for N-1A LLM enrichment.

Pulls a recent N-1A filing from SEC EDGAR, runs the enricher against the real
LLM endpoint configured in .env, and prints the extracted fields. Hits both
the SEC and the LLM API — this is intentionally a live test, not a mock.

Run with:
    python -m tests.test_n1a_enrichment
"""

import logging
import sys
from datetime import date, timedelta

from config import LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL
from sec.client import EdgarClient
from sec.parsers import parse_daily_index
from pipeline.enricher import enrich_n1a, fetch_n1a_text, extract_fields_from_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_enrich")


def find_recent_n1a(client: EdgarClient, lookback_days: int = 90):
    """Walk back day-by-day until we find an N-1A-style filing.

    Initial N-1A filings are rare (only when a brand-new fund family registers).
    Fall back to N-1A/A and 485BPOS — both reuse the prospectus narrative the
    enricher is designed to parse.
    """
    preferred_order = ["N-1A", "N-1A/A", "485BPOS"]
    today = date.today()
    seen_alt = None
    for offset in range(lookback_days):
        d = today - timedelta(days=offset)
        if d.weekday() >= 5:
            continue
        raw = client.fetch_daily_index(d)
        if not raw:
            continue
        records = parse_daily_index(raw)
        for form in preferred_order:
            matches = [r for r in records if r.form_type == form]
            if matches:
                log.info("Found %d %s filings on %s", len(matches), form, d.isoformat())
                if form == "N-1A":
                    return matches[0]
                if seen_alt is None:
                    seen_alt = matches[0]
                # Keep scanning for an actual N-1A but remember the fallback.
                break
    if seen_alt is not None:
        log.info("No fresh N-1A found; using fallback %s filing for %s",
                 seen_alt.form_type, seen_alt.entity_name)
    return seen_alt


def main() -> int:
    log.info("LLM endpoint: %s", LLM_API_BASE_URL or "https://api.openai.com (default)")
    log.info("LLM model:    %s", LLM_MODEL)
    if not LLM_API_KEY:
        log.error("LLM_API_KEY is empty — set it in .env before running this test.")
        return 2

    client = EdgarClient()
    record = find_recent_n1a(client)
    if not record:
        log.error("No N-1A filings found in the last 3 weeks of daily indexes.")
        return 1

    log.info("Selected filing:")
    log.info("  fund:       %s", record.entity_name)
    log.info("  cik:        %s", record.cik)
    log.info("  accession:  %s", record.accession_number)
    log.info("  filing_date %s", record.filing_date)
    log.info("  edgar_url:  %s", record.edgar_url)

    log.info("Fetching N-1A document text from EDGAR...")
    text = fetch_n1a_text(record.cik, record.accession_number, client=client)
    if not text:
        log.error("Could not fetch N-1A document text.")
        return 1
    log.info("Fetched %d chars of prospectus text. First 200 chars:\n%s\n...", len(text), text[:200])

    log.info("Calling LLM to extract fields...")
    fields = extract_fields_from_text(text)

    log.info("=" * 60)
    log.info("EXTRACTED FIELDS")
    log.info("=" * 60)
    populated = 0
    for k, v in fields.items():
        marker = "  " if v is None else "* "
        if v is not None:
            populated += 1
        log.info("%s%-20s %s", marker, k + ":", v)
    log.info("=" * 60)
    log.info("Populated %d / %d fields", populated, len(fields))

    if populated == 0:
        log.warning("No fields populated — check the document text or prompt.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
