"""Configuration loader — reads .env and defines project-wide constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent

# Load .env file
load_dotenv(PROJECT_ROOT / ".env")

# --- SEC EDGAR ---
SEC_USER_AGENT_NAME = os.getenv("SEC_USER_AGENT_NAME", "DefaultName")
SEC_USER_AGENT_EMAIL = os.getenv("SEC_USER_AGENT_EMAIL", "default@example.com")
SEC_USER_AGENT = f"{SEC_USER_AGENT_NAME} {SEC_USER_AGENT_EMAIL}"

# EDGAR base URLs
EDGAR_BASE_URL = "https://www.sec.gov"
EDGAR_FULL_INDEX_URL = f"{EDGAR_BASE_URL}/Archives/edgar/daily-index"
EDGAR_ARCHIVES_URL = f"{EDGAR_BASE_URL}/Archives/edgar/data"

# Rate limit: SEC allows max 10 requests/second
SEC_REQUEST_DELAY = 0.12  # seconds between requests (~8 req/s, safe margin)

# --- Database ---
DB_PATH = PROJECT_ROOT / os.getenv("DB_PATH", "db/ipo_etf_tracker.db")

# --- Filing form types ---
# Stock IPO forms
IPO_FORM_TYPES = {
    "S-1",      # Initial registration statement
    "S-1/A",    # Amendment to S-1
    "F-1",      # Foreign private issuer registration
    "F-1/A",    # Amendment to F-1
    "424B1",    # Final prospectus (Rule 424(b)(1))
    "424B2",    # Final prospectus (Rule 424(b)(2))
    "424B3",    # Final prospectus (Rule 424(b)(3))
    "424B4",    # Final prospectus (Rule 424(b)(4))
    "EFFECT",   # Notice of effectiveness
}

# ETF launch forms
ETF_FORM_TYPES = {
    "N-1A",     # Registration for open-end management investment companies
    "N-1A/A",   # Amendment to N-1A
    "485BPOS",  # Post-effective amendment (auto-effective)
    "485APOS",  # Post-effective amendment (SEC review required)
    "497",      # Definitive materials
    "497K",     # Summary prospectus
    "8-A12B",   # Registration under Securities Exchange Act
}

# All monitored forms
ALL_FORM_TYPES = IPO_FORM_TYPES | ETF_FORM_TYPES

# --- Lifecycle statuses ---
STATUS_FILED = "FILED"
STATUS_AMENDED = "AMENDED"
STATUS_PRICED = "PRICED"
STATUS_EFFECTIVE = "EFFECTIVE"
STATUS_LAUNCHED = "LAUNCHED"
STATUS_COMPLETED = "COMPLETED"  # After moved to active_securities

# Form type → status mapping
FORM_TO_STATUS = {
    # IPO forms
    "S-1": STATUS_FILED,
    "F-1": STATUS_FILED,
    "S-1/A": STATUS_AMENDED,
    "F-1/A": STATUS_AMENDED,
    "424B1": STATUS_PRICED,
    "424B2": STATUS_PRICED,
    "424B3": STATUS_PRICED,
    "424B4": STATUS_PRICED,
    "EFFECT": STATUS_EFFECTIVE,
    # ETF forms
    "N-1A": STATUS_FILED,
    "N-1A/A": STATUS_AMENDED,
    "485APOS": STATUS_AMENDED,
    "485BPOS": STATUS_EFFECTIVE,
    "497": STATUS_PRICED,
    "497K": STATUS_PRICED,
    "8-A12B": STATUS_EFFECTIVE,
}

# Status ordering for lifecycle advancement (higher index = further along)
STATUS_ORDER = {
    STATUS_FILED: 0,
    STATUS_AMENDED: 1,
    STATUS_PRICED: 2,
    STATUS_EFFECTIVE: 3,
    STATUS_LAUNCHED: 4,
    STATUS_COMPLETED: 5,
}
