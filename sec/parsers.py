"""Parsing logic for EDGAR daily index files and filing documents."""

import re
import logging
from dataclasses import dataclass, field

from config import (
    ALL_FORM_TYPES,
    IPO_FORM_TYPES,
    ETF_FORM_TYPES,
    EDGAR_BASE_URL,
)

logger = logging.getLogger(__name__)


@dataclass
class FilingRecord:
    """Represents a single filing from the daily index."""

    form_type: str
    entity_name: str
    cik: str
    filing_date: str
    accession_number: str
    edgar_url: str = ""
    sic_code: str = ""
    entity_type: str = ""  # 'IPO' or 'ETF'

    def __post_init__(self):
        # Determine if this is an IPO or ETF filing
        if not self.entity_type:
            if self.form_type in IPO_FORM_TYPES:
                self.entity_type = "IPO"
            elif self.form_type in ETF_FORM_TYPES:
                self.entity_type = "ETF"

        # Build EDGAR URL if not provided
        if not self.edgar_url and self.cik and self.accession_number:
            acc_no_dashes = self.accession_number.replace("-", "")
            self.edgar_url = (
                f"{EDGAR_BASE_URL}/Archives/edgar/data/"
                f"{self.cik}/{acc_no_dashes}/{self.accession_number}-index.htm"
            )


def parse_daily_index(raw_text: str) -> list[FilingRecord]:
    """
    Parse a EDGAR master daily index file (master.YYYYMMDD.idx format).

    The master index is pipe-delimited with columns:
        CIK|Company Name|Form Type|Date Filed|Filename

    Header lines are separated by a dashed line (----------).
    We skip everything until we find the dashed separator line,
    then parse the data rows below it.

    Returns a list of FilingRecord objects for monitored form types only.
    """
    records = []
    lines = raw_text.strip().split("\n")

    # Find the separator line (dashes)
    data_start = 0
    for i, line in enumerate(lines):
        if re.match(r"^-{5,}", line.strip()):
            data_start = i + 1
            break

    if data_start == 0:
        logger.warning("Could not find data separator in daily index")
        return records

    for line in lines[data_start:]:
        if not line.strip():
            continue

        # Master index is pipe-delimited:
        # CIK|Company Name|Form Type|Date Filed|Filename
        parts = line.split("|")
        if len(parts) < 5:
            continue

        cik = parts[0].strip()
        entity_name = parts[1].strip()
        form_type = parts[2].strip()
        filing_date = parts[3].strip()
        filename = parts[4].strip()

        # Only keep monitored form types
        if form_type not in ALL_FORM_TYPES:
            continue

        # Convert date from YYYYMMDD to YYYY-MM-DD if needed
        if len(filing_date) == 8 and filing_date.isdigit():
            filing_date = f"{filing_date[:4]}-{filing_date[4:6]}-{filing_date[6:]}"

        # Extract accession number from filename
        # Filename format: edgar/data/CIK/ACCESSION-NUMBER.txt
        accession_match = re.search(
            r"edgar/data/\d+/([\d-]+)", filename
        )
        accession_number = accession_match.group(1) if accession_match else ""
        # Remove trailing .txt if present in accession number
        accession_number = accession_number.replace(".txt", "")

        record = FilingRecord(
            form_type=form_type,
            entity_name=entity_name,
            cik=cik,
            filing_date=filing_date,
            accession_number=accession_number,
        )
        records.append(record)

    logger.info(
        "Parsed %d relevant filings from daily index (%d total lines)",
        len(records),
        len(lines) - data_start,
    )
    return records
