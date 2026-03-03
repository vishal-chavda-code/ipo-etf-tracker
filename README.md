# IPO & ETF Launch Tracker

A Python pipeline that monitors SEC EDGAR daily index filings for **stock IPOs** and **ETF launches**, tracks their full lifecycle from first registration through launch, and stores everything in a local SQLite database for exploration via Jupyter Notebook.

---

## Overview

### What It Does

1. **Daily Batch Ingestion** — Downloads the SEC EDGAR daily index file (published ~10 PM ET), parses it for IPO/ETF-related form types, and inserts new entities into the database.
2. **Lifecycle Tracking** — Each entity progresses through statuses: `FILED → AMENDED → PRICED → EFFECTIVE → LAUNCHED`. Every daily run advances the status as new filings appear.
3. **Event Log** — Every individual filing (S-1, S-1/A, 424B, EFFECT, N-1A, 485BPOS, etc.) is recorded in a `filing_events` table, providing a full audit trail.
4. **Notifications** — When an entity reaches `LAUNCHED` status, a row is inserted into the `notifications` table and the entity is moved to the `active_securities` table.
5. **Exploration** — A Jupyter Notebook connects to the SQLite DB for interactive querying, filtering, and visual exploration of the pipeline and active tables.

### Lifecycle Model

```
FILED ──► AMENDED ──► PRICED ──► EFFECTIVE ──► LAUNCHED
  │          │           │           │              │
  │          │           │           │              ▼
  │          │           │           │        active_securities
  │          │           │           │        (auto-moved)
  └──────────┴───────────┴───────────┴──────────────┘
                  filing_events (audit log)
```

---

## Project Structure & File Types

```
IPO_ETF/
│
├── README.md                  # This file — project overview and documentation
├── requirements.txt           # Python package dependencies (pip install -r)
├── .env.example               # Template for environment variables (copy to .env)
├── .env                       # Local env vars — SEC credentials (NOT committed)
├── .gitignore                 # Git ignore rules (venv, .env, db files, etc.)
│
├── config.py                  # Configuration loader — reads .env, defines constants
├── main.py                    # Entry point — runs the daily batch pipeline
│
├── db/                        # Database layer
│   ├── __init__.py            # Package init
│   ├── models.py              # SQLite table schemas (CREATE TABLE statements)
│   ├── operations.py          # CRUD operations (insert, update, query helpers)
│   └── ipo_etf_tracker.db     # SQLite database file (auto-created, NOT committed)
│
├── sec/                       # SEC EDGAR integration
│   ├── __init__.py            # Package init
│   ├── client.py              # HTTP client for EDGAR daily index downloads
│   └── parsers.py             # Parsing logic for daily index + filing documents
│
├── pipeline/                  # Core pipeline logic
│   ├── __init__.py            # Package init
│   ├── ingester.py            # Ingests parsed filings into the database
│   ├── lifecycle.py           # Advances entity status based on new filings
│   └── notifier.py            # Handles launch detection → notifications + active table
│
├── notebooks/                 # Jupyter notebooks for data exploration
│   └── explorer.ipynb         # Interactive notebook to query & visualize DB tables
│
├── docs/                      # Additional documentation (if needed)
│
└── venv/                      # Python virtual environment (NOT committed)
```

### File Type Reference

| Extension   | Type               | Purpose                                                   |
|-------------|--------------------|------------------------------------------------------------|
| `.py`       | Python source      | All application logic, database ops, SEC client, pipeline |
| `.md`       | Markdown           | Documentation (this README)                                |
| `.txt`      | Plain text         | `requirements.txt` — pip dependency list                  |
| `.env`      | Environment file   | Local secrets (SEC User-Agent name/email)                 |
| `.gitignore`| Git config         | Specifies files/folders excluded from version control      |
| `.ipynb`    | Jupyter Notebook   | Interactive data exploration and table viewing             |
| `.db`       | SQLite database    | Local database storing all IPO/ETF/event/notification data |

---

## Database Schema

### `stock_ipos` — IPO pipeline tracker

| Column            | Type     | Description                                      |
|-------------------|----------|--------------------------------------------------|
| `id`              | INTEGER  | Primary key (auto-increment)                      |
| `entity_name`     | TEXT     | Company name (from filing, available before ticker)|
| `ticker`          | TEXT     | Ticker symbol (NULL until assigned)                |
| `cik`             | TEXT     | SEC Central Index Key                              |
| `status`          | TEXT     | Current lifecycle status (FILED→LAUNCHED)          |
| `form_type`       | TEXT     | Initial filing form type (e.g., S-1)              |
| `filing_date`     | TEXT     | Date of first filing                               |
| `effective_date`  | TEXT     | Date SEC declared effective (NULL until known)     |
| `launch_date`     | TEXT     | Actual IPO/trading date (NULL until launched)      |
| `price`           | REAL     | IPO price (NULL until priced)                      |
| `exchange`        | TEXT     | Target exchange (e.g., NYSE, NASDAQ)               |
| `sic_code`        | TEXT     | Standard Industrial Classification code            |
| `edgar_url`       | TEXT     | URL to EDGAR filing page                           |
| `created_at`      | TEXT     | Row creation timestamp                             |
| `updated_at`      | TEXT     | Last update timestamp                              |

### `etf_launches` — ETF pipeline tracker

| Column            | Type     | Description                                      |
|-------------------|----------|--------------------------------------------------|
| `id`              | INTEGER  | Primary key (auto-increment)                      |
| `fund_name`       | TEXT     | ETF/fund name (from filing)                       |
| `ticker`          | TEXT     | Ticker symbol (NULL until assigned)                |
| `cik`             | TEXT     | SEC Central Index Key                              |
| `status`          | TEXT     | Current lifecycle status (FILED→LAUNCHED)          |
| `form_type`       | TEXT     | Initial filing form type (e.g., N-1A)             |
| `filing_date`     | TEXT     | Date of first filing                               |
| `effective_date`  | TEXT     | Date SEC declared effective (NULL until known)     |
| `launch_date`     | TEXT     | Actual ETF trading start date (NULL until launched)|
| `exchange`        | TEXT     | Target exchange                                    |
| `issuer`          | TEXT     | Fund sponsor/issuer company                        |
| `edgar_url`       | TEXT     | URL to EDGAR filing page                           |
| `created_at`      | TEXT     | Row creation timestamp                             |
| `updated_at`      | TEXT     | Last update timestamp                              |

### `filing_events` — Audit log of every filing

| Column            | Type     | Description                                      |
|-------------------|----------|--------------------------------------------------|
| `id`              | INTEGER  | Primary key                                        |
| `entity_type`     | TEXT     | 'IPO' or 'ETF'                                    |
| `entity_id`       | INTEGER  | FK to stock_ipos.id or etf_launches.id            |
| `form_type`       | TEXT     | SEC form type (S-1, S-1/A, 424B4, N-1A, etc.)    |
| `filing_date`     | TEXT     | Filing date                                        |
| `accession_number`| TEXT     | SEC accession number (unique filing ID)            |
| `edgar_url`       | TEXT     | Direct URL to filing                               |
| `description`     | TEXT     | Brief description of the filing                    |
| `created_at`      | TEXT     | Row creation timestamp                             |

### `active_securities` — Launched entities (action table)

| Column            | Type     | Description                                      |
|-------------------|----------|--------------------------------------------------|
| `id`              | INTEGER  | Primary key                                        |
| `entity_type`     | TEXT     | 'IPO' or 'ETF'                                    |
| `entity_name`     | TEXT     | Company/fund name                                  |
| `ticker`          | TEXT     | Ticker symbol                                      |
| `launch_date`     | TEXT     | Date launched/started trading                      |
| `source_id`       | INTEGER  | Original ID from stock_ipos or etf_launches       |
| `created_at`      | TEXT     | Row creation timestamp                             |

### `notifications` — Launch alerts

| Column            | Type     | Description                                      |
|-------------------|----------|--------------------------------------------------|
| `id`              | INTEGER  | Primary key                                        |
| `entity_type`     | TEXT     | 'IPO' or 'ETF'                                    |
| `entity_name`     | TEXT     | Company/fund name                                  |
| `ticker`          | TEXT     | Ticker symbol                                      |
| `message`         | TEXT     | Human-readable notification message                |
| `is_read`         | INTEGER  | 0 = unread, 1 = read                              |
| `created_at`      | TEXT     | Row creation timestamp                             |

---

## SEC Filing Types Monitored

### Stock IPO Filings

| Form Type  | Description                                           | Lifecycle Signal  |
|------------|-------------------------------------------------------|-------------------|
| `S-1`      | Initial registration statement                        | → `FILED`         |
| `S-1/A`    | Amendment to registration                             | → `AMENDED`       |
| `F-1`      | Registration for foreign private issuers              | → `FILED`         |
| `F-1/A`    | Amendment to foreign registration                     | → `AMENDED`       |
| `424B1-4`  | Final prospectus (various types, includes pricing)    | → `PRICED`        |
| `EFFECT`   | SEC declares registration effective                   | → `EFFECTIVE`     |

### ETF Launch Filings

| Form Type   | Description                                          | Lifecycle Signal  |
|-------------|------------------------------------------------------|-------------------|
| `N-1A`      | Registration for open-end funds (mutual funds/ETFs)  | → `FILED`         |
| `N-1A/A`    | Amendment to N-1A                                    | → `AMENDED`       |
| `485BPOS`   | Post-effective amendment (auto-effective)             | → `EFFECTIVE`     |
| `485APOS`   | Post-effective amendment (requires SEC review)        | → `AMENDED`       |
| `497`       | Definitive materials / final prospectus              | → `PRICED`        |
| `497K`      | Summary prospectus                                   | → `PRICED`        |
| `8-A12B`    | Registration under Exchange Act (exchange listing)    | → `EFFECTIVE`     |

---

## Setup & Usage

### 1. Clone and set up environment

```bash
cd IPO_ETF
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
# Copy the template
cp .env.example .env

# Edit .env with your info (required by SEC EDGAR):
# SEC_USER_AGENT_NAME=Your Name
# SEC_USER_AGENT_EMAIL=you@email.com
```

### 3. Initialize the database

```bash
python main.py --init
```

### 4. Run the daily batch

```bash
# Fetch today's filings and process
python main.py --run

# Backfill last N days
python main.py --backfill 14
```

### 5. Explore the data

Open `notebooks/explorer.ipynb` in VS Code or JupyterLab to interactively query and view all tables.

---

## Data Flow

```
SEC EDGAR Daily Index
        │
        ▼
  sec/client.py          ← Downloads daily-index.json
        │
        ▼
  sec/parsers.py         ← Filters for IPO/ETF form types, extracts metadata
        │
        ▼
  pipeline/ingester.py   ← Creates new rows or matches to existing entities
        │
        ▼
  pipeline/lifecycle.py  ← Advances status (FILED → AMENDED → ... → LAUNCHED)
        │
        ▼
  pipeline/notifier.py   ← On LAUNCHED: insert notification + move to active_securities
        │
        ▼
  SQLite DB              ← stock_ipos, etf_launches, filing_events,
                            active_securities, notifications
```

---

## Notes

- **Rate limiting**: SEC EDGAR allows max **10 requests/second**. The client enforces this.
- **2-week backfill**: On first run, use `--backfill 14` to catch recent filings.
- **Ticker may be NULL**: Many filings appear before a ticker is assigned. The entity name (company/fund name) is always available and is the primary identifier early in the lifecycle.
- **Database location**: `db/ipo_etf_tracker.db` — auto-created on first run.
