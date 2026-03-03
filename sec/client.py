"""HTTP client for downloading SEC EDGAR daily index files."""

import time
import logging
from datetime import date, timedelta
from pathlib import Path

import requests

from config import (
    EDGAR_FULL_INDEX_URL,
    EDGAR_BASE_URL,
    SEC_USER_AGENT,
    SEC_REQUEST_DELAY,
)

logger = logging.getLogger(__name__)


class EdgarClient:
    """Handles HTTP communication with SEC EDGAR."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Host": "www.sec.gov",
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce SEC rate limit (max 10 req/sec)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < SEC_REQUEST_DELAY:
            time.sleep(SEC_REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str) -> requests.Response:
        """Make a rate-limited GET request."""
        self._rate_limit()
        logger.debug("GET %s", url)
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp

    def fetch_daily_index(self, target_date: date) -> str:
        """
        Fetch the master daily index file for a given date.

        EDGAR daily index path format:
            /Archives/edgar/daily-index/{YYYY}/QTR{Q}/master.{YYYYMMDD}.idx

        The master index is pipe-delimited:
            CIK|Company Name|Form Type|Date Filed|Filename

        Returns the raw text content of the index file.
        """
        quarter = (target_date.month - 1) // 3 + 1
        date_str = target_date.strftime("%Y%m%d")
        year = target_date.year

        url = (
            f"{EDGAR_FULL_INDEX_URL}/{year}/QTR{quarter}/"
            f"master.{date_str}.idx"
        )

        try:
            resp = self.get(url)
            logger.info(
                "Fetched daily index for %s (%d bytes)",
                target_date.isoformat(),
                len(resp.text),
            )
            return resp.text
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404):
                logger.warning(
                    "No daily index found for %s (HTTP %d — likely a weekend/holiday)",
                    target_date.isoformat(),
                    e.response.status_code,
                )
                return ""
            raise

    def fetch_daily_index_range(self, start_date: date, end_date: date) -> dict[date, str]:
        """
        Fetch daily index files for a range of dates.

        Returns a dict mapping date → raw index text (skips empty/missing days).
        """
        results = {}
        current = start_date
        while current <= end_date:
            text = self.fetch_daily_index(current)
            if text:
                results[current] = text
            current += timedelta(days=1)
        return results

    def fetch_filing_page(self, cik: str, accession_number: str) -> str:
        """
        Fetch the filing index page for a specific filing.

        Returns the HTML content of the filing page.
        """
        # Accession number formatted without dashes for URL path
        acc_no_dashes = accession_number.replace("-", "")
        url = (
            f"{EDGAR_BASE_URL}/Archives/edgar/data/"
            f"{cik}/{acc_no_dashes}/{accession_number}-index.htm"
        )
        resp = self.get(url)
        return resp.text
