# SEC EDGAR Filing Landscape

*A Practitioner's Guide to Filing Types, CIK Codes, and the IPO/ETF Launch Pipeline*

*March 2026 | Prepared for IPO & ETF Launch Tracker Project*

---

## 1. What Is EDGAR and Why It Matters

EDGAR (Electronic Data Gathering, Analysis, and Retrieval) is the SEC's mandatory electronic filing system. Every public company, mutual fund, ETF, and registered investment vehicle in the United States must file disclosure documents through EDGAR. It went live in 1996 and now processes over 500,000 filings per year.

For the purposes of tracking IPOs and ETF launches, EDGAR is the single source of truth. Every step of the registration process — from initial filing through SEC effectiveness — is recorded as a discrete filing event with a unique accession number. By monitoring the daily index of new filings, you can detect new issuers entering the market before they show up on Bloomberg or any news feed.

### How the Daily Index Works

Every business day around 10 PM ET, EDGAR publishes a master daily index file that lists every filing received that day. The file is pipe-delimited with five columns:

**`CIK | Company Name | Form Type | Date Filed | Filename`**

The pipeline downloads this file, filters for relevant form types (S-1, N-1A, etc.), and processes each matching row. The daily index is the entry point for the entire system — everything downstream depends on it.

The index URL follows a predictable pattern: `/Archives/edgar/daily-index/{YYYY}/QTR{Q}/master.{YYYYMMDD}.idx`. Quarters are calendar quarters (QTR1 = Jan–Mar, QTR2 = Apr–Jun, etc.). Weekends and federal holidays have no index file, so the pipeline handles 403/404 responses gracefully.

---

## 2. CIK Codes: The Universal Identifier

The Central Index Key (CIK) is a unique numeric identifier that the SEC assigns to every entity that files with EDGAR. It's the closest thing EDGAR has to a primary key. A CIK is assigned once and never changes, even if the company changes its name, ticker, or corporate structure.

### Key Properties of CIK Codes

- **Permanent and immutable.** Once assigned, a CIK stays with the entity forever. If Company A acquires Company B, both retain their original CIKs. Company B's CIK simply stops receiving new filings.
- **One entity, one CIK.** Each legal entity gets exactly one CIK. A parent company and its subsidiary have separate CIKs. An ETF trust (like "iShares Trust") has one CIK that covers all the individual funds within it.
- **Available before ticker assignment.** CIK is assigned when the entity first registers with the SEC, which can be months before a ticker symbol is assigned. This is why the pipeline tracks entities by CIK and entity name initially — the ticker may not exist yet.
- **Numeric, variable length.** CIKs range from 1 to 10 digits. In EDGAR URLs they're often zero-padded to 10 digits (e.g., 0001234567), but in the daily index they appear without padding.

### CIK vs. Ticker: Why Both Matter

Tickers are assigned by exchanges (NYSE, NASDAQ) and can change. CIKs are assigned by the SEC and cannot. The pipeline uses CIK as the primary deduplication key because the same company might file under different name variations across filings, but the CIK is always consistent. The ticker, when it eventually appears, gets populated later in the lifecycle.

You can look up any CIK at `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_number}`. This returns the entity's complete filing history.

---

## 3. Stock IPO Filing Types

An IPO (Initial Public Offering) follows a well-defined SEC registration process. Each step generates a specific form type that signals where the issuer is in the pipeline.

### S-1: Initial Registration Statement

The S-1 is the starting gun. When a private U.S. company decides to go public, they file an S-1 registration statement with the SEC. This is a comprehensive document that includes the company's financial statements, business description, risk factors, management bios, and proposed use of proceeds. It can run hundreds of pages.

The S-1 is filed under the Securities Act of 1933, which requires any offer or sale of securities to be registered. Filing the S-1 makes the company's intention to go public a matter of public record, even though the offering hasn't happened yet.

**Lifecycle signal: FILED.** This is the earliest detectable signal that a company intends to IPO.

### F-1: Foreign Private Issuer Registration

The F-1 is the international equivalent of the S-1. It's used by foreign private issuers — companies incorporated outside the United States that want to sell shares on U.S. exchanges. The content requirements are similar to S-1 but allow some accommodations for different accounting standards (IFRS vs. U.S. GAAP).

Many Chinese, Israeli, and European tech companies use F-1 filings to list on NASDAQ or NYSE. If you see an F-1, you're looking at a foreign company entering U.S. capital markets.

**Lifecycle signal: FILED.**

### S-1/A and F-1/A: Amendments

After the initial S-1 or F-1 is filed, the SEC staff reviews it and sends a comment letter with questions and requests for clarification. The company responds by filing an amendment (S-1/A or F-1/A) with revised or updated information. This back-and-forth can happen multiple times — it's not unusual to see 3–5 amendments before the SEC is satisfied.

Each amendment typically narrows the price range, updates financials, and addresses SEC comments. The presence of amendments is a positive signal — it means the SEC is actively reviewing and the deal is progressing.

**Lifecycle signal: AMENDED.**

### 424B (B1 through B4): Final Prospectus

The 424B series filings are the final prospectus — the definitive offering document that includes the actual IPO price, number of shares being sold, and underwriter details. Different variants exist based on which subsection of Rule 424(b) they fall under:

- **424B1:** Prospectus filed under Rule 424(b)(1) — used when the prospectus isn't substantially different from the version in the registration statement.
- **424B2:** The most common variant. Used for structured notes, debt offerings, and some equity deals. This is the one that creates noise in the pipeline because banks like Royal Bank of Canada and Barclays file 424B2s constantly for structured products.
- **424B3:** Used when the prospectus is being filed for the first time and wasn't included in the registration statement.
- **424B4:** The most common for traditional equity IPOs. Filed after the registration statement is effective, containing the final pricing.

The key insight: a 424B4 from a company that already has an S-1 in the database is a strong "priced" signal. A 424B2 from an entity with no prior S-1 is almost certainly a structured note issuance by an existing public company — not an IPO.

**Lifecycle signal: PRICED.**

### EFFECT: Notice of Effectiveness

When the SEC staff completes its review and is satisfied that the registration statement meets all disclosure requirements, it "declares the registration statement effective." This is filed as an EFFECT notice. It means the company is legally cleared to sell the registered securities.

An EFFECT filing doesn't mean the company has started trading — it means they're allowed to. The actual first trading day is usually 1–3 business days after effectiveness, depending on the underwriter's timeline. EFFECT notices have accession numbers starting with `9999999995`, which is how the SEC distinguishes them from regular filings.

**Lifecycle signal: EFFECTIVE.**

### IPO Filing Types Summary

| Form Type | Description | Lifecycle Signal | Key Details |
|-----------|-------------|------------------|-------------|
| S-1 | Initial registration (U.S. company) | FILED | First signal of IPO intent; comprehensive disclosure |
| F-1 | Initial registration (foreign issuer) | FILED | International equivalent of S-1 |
| S-1/A | Amendment to S-1 | AMENDED | SEC comment resolution; may appear 3–5 times |
| F-1/A | Amendment to F-1 | AMENDED | Same as S-1/A for foreign issuers |
| 424B1 | Final prospectus (Rule 424(b)(1)) | PRICED | Less common variant |
| 424B2 | Final prospectus (Rule 424(b)(2)) | PRICED | High noise: banks use for structured notes |
| 424B3 | Final prospectus (Rule 424(b)(3)) | PRICED | First-time prospectus filing |
| 424B4 | Final prospectus (Rule 424(b)(4)) | PRICED | Most common for traditional equity IPOs |
| EFFECT | SEC declares registration effective | EFFECTIVE | Accession starts with 9999999995 |

---

## 4. ETF Launch Filing Types

ETFs (Exchange-Traded Funds) follow a different registration path than stock IPOs because they're registered under the Investment Company Act of 1940 rather than (or in addition to) the Securities Act of 1933. The filing types reflect this dual regulatory framework.

### N-1A: Registration for Open-End Funds

The N-1A is the ETF equivalent of the S-1. It's the registration statement for open-end management investment companies, which includes both traditional mutual funds and ETFs. The N-1A contains the fund's investment objectives, strategies, risks, fees, and performance data.

One critical nuance: a single N-1A is often filed by a trust or fund family (like "iShares Trust" or "Invesco ETF Trust") that serves as an umbrella for dozens of individual funds. The CIK belongs to the trust, not the individual ETF. This means the pipeline tracks at the trust level initially — individual fund-level tracking would require parsing the N-1A document itself to extract series-level data.

**Lifecycle signal: FILED.**

### N-1A/A: Amendment to N-1A

Same concept as S-1/A. The fund family files amendments in response to SEC comments or to update disclosures. For new ETFs, this is a progression signal. For existing fund families adding new series, it may just be routine maintenance.

**Lifecycle signal: AMENDED.**

### 485BPOS: Post-Effective Amendment (Auto-Effective)

This is the highest-noise form type in the ETF space. A 485BPOS is a post-effective amendment that becomes effective automatically upon filing. Existing fund families file these routinely — sometimes annually — to update prospectuses, add new share classes, or reflect fee changes. Vanguard, BlackRock, and Fidelity each file dozens of 485BPOS filings per year across their fund families.

The problem for the pipeline: a 485BPOS from an entity without a prior N-1A in the database is almost certainly an existing fund family doing routine updates, not a new ETF launch. This is the ETF equivalent of the 424B2 noise on the IPO side, and it's why the initial-registration-only entity creation rule is essential.

**Lifecycle signal: EFFECTIVE.**

### 485APOS: Post-Effective Amendment (SEC Review Required)

Unlike 485BPOS, a 485APOS requires SEC review before it becomes effective. Fund families use this when making material changes that the SEC needs to approve — like launching an entirely new fund series under an existing trust, changing fundamental investment policies, or restructuring the fund. Because it requires SEC review, it's a more meaningful signal than 485BPOS for tracking genuine new activity.

**Lifecycle signal: AMENDED.**

### 497 and 497K: Definitive Materials

Form 497 is used to file definitive fund materials — typically the final prospectus or supplements. Form 497K is the summary prospectus, a shorter document required under SEC rules that gives investors the key facts about a fund in a standardized format.

These filings indicate the fund is finalizing its offering documents, which typically happens just before or at launch. However, like 485BPOS, existing funds file 497s routinely when updating prospectuses, so they're noisy as standalone signals.

**Lifecycle signal: PRICED.**

### 8-A12B: Registration Under the Exchange Act

This is a strong signal. The 8-A12B registers a class of securities under Section 12(b) of the Securities Exchange Act of 1934, which is required for listing on a national exchange. When an ETF files an 8-A12B, it means the fund has applied for exchange listing — it's one of the final steps before trading begins.

An 8-A12B from an entity already in the pipeline (tracked from a prior N-1A) is a high-confidence effectiveness signal. If you see an 8-A12B for an entity you're not tracking, it could be an existing fund changing its exchange listing.

**Lifecycle signal: EFFECTIVE.**

### ETF Filing Types Summary

| Form Type | Description | Lifecycle Signal | Key Details |
|-----------|-------------|------------------|-------------|
| N-1A | Registration for open-end funds | FILED | Filed by trust (umbrella) not individual fund |
| N-1A/A | Amendment to N-1A | AMENDED | SEC comment responses or disclosure updates |
| 485BPOS | Post-effective amendment (auto) | EFFECTIVE | Highest noise: routine annual updates by fund families |
| 485APOS | Post-effective amendment (SEC review) | AMENDED | More meaningful: requires SEC approval |
| 497 | Definitive prospectus materials | PRICED | Final offering documents |
| 497K | Summary prospectus | PRICED | Standardized key-facts document |
| 8-A12B | Exchange Act registration | EFFECTIVE | Strong signal: exchange listing application |

---

## 5. The Lifecycle Model

The pipeline maps SEC filings to a five-stage lifecycle. Understanding why each stage exists helps you interpret the data correctly and identify where the model's assumptions break down.

### FILED → AMENDED → PRICED → EFFECTIVE → LAUNCHED

- **FILED:** The entity has submitted its initial registration (S-1, F-1, or N-1A). This is the earliest public signal of intent. At this stage, there's no guarantee the offering will proceed — companies can and do withdraw S-1 filings.
- **AMENDED:** The entity is in active dialogue with the SEC. Amendments (S-1/A, F-1/A, N-1A/A, 485APOS) indicate the registration is progressing. Multiple amendments are normal and expected.
- **PRICED:** A final prospectus has been filed (424B series, 497, 497K) that includes or implies definitive terms. For equity IPOs, this typically means the price has been set. For ETFs, it means the offering documents are finalized.
- **EFFECTIVE:** The SEC has declared the registration effective (EFFECT notice, 485BPOS auto-effectiveness, or 8-A12B exchange registration). The security is legally cleared for sale/trading.
- **LAUNCHED:** The pipeline's terminal state. Currently triggered when an entity reaches EFFECTIVE, under the assumption that SEC effectiveness means trading is imminent. In reality, there can be a 1–3 day gap between effectiveness and first trading day.

### Known Limitations

The lifecycle model makes a simplifying assumption: EFFECTIVE = LAUNCHED. In practice, some registrations become effective but the offering is delayed or withdrawn. A more robust pipeline would cross-reference against exchange listing data or market data feeds to confirm actual first-trade dates. Additionally, the status only advances forward — there's no mechanism to handle withdrawn or abandoned registrations, which is a real-world edge case worth addressing eventually.

---

## 6. Noise Sources and Edge Cases

The biggest operational challenge in this pipeline isn't the parsing or the database — it's separating genuine new issuances from the massive volume of routine filings by existing entities.

### Structured Note Issuers (424B2 Noise)

Large banks — Royal Bank of Canada, Barclays, Goldman Sachs, Morgan Stanley — file hundreds of 424B2 prospectuses per year for structured notes, market-linked CDs, and other derivative products. Each is technically a new securities offering, but they're not IPOs in any meaningful sense. These entities have been public for decades.

**The fix:** Only create entities on initial registration forms. If a 424B2 arrives and there's no prior S-1/F-1 for that CIK, skip it.

### Fund Family Maintenance (485BPOS Noise)

Fund trusts like "Vanguard Chester Funds" or "Fidelity Advisor Series" file 485BPOS amendments routinely. These are existing fund families updating prospectuses, not launching new ETFs. The same fix applies: only create ETF entities on N-1A initial registrations.

### Shell Companies and SPACs

The data shows several SPAC (Special Purpose Acquisition Company) registrations — entities like "Plutonian Acquisition Corp. II" and "Dune Acquisition Corp III." SPACs file S-1s because they are technically IPO'ing, but they're blank-check companies that haven't yet identified an acquisition target. Depending on your use case, you may want to flag or filter these separately. SPACs typically have "Acquisition Corp," "Capital Corp," or similar strings in their entity names.

### Existing Companies Filing S-1s

Not every S-1 is an IPO. Already-public companies sometimes file S-1 registration statements for secondary offerings, employee stock plans, or resale registrations. The pipeline will pick these up as new entities if the company hasn't filed an S-1 previously within the backfill window. To handle this properly, you'd need to cross-reference against a database of already-public companies or check whether the CIK has prior 10-K/10-Q filings (which only public companies file).

---

## 7. Accession Numbers and EDGAR URLs

Every filing submitted to EDGAR receives a unique accession number. It's the filing-level primary key and is formatted as: `FILER_ID-YY-SEQUENCE` (e.g., `0001193125-26-004521`).

### Anatomy of an Accession Number

- **First 10 digits (0001193125):** The CIK of the filing agent or filer. Large filing agents like EDGAR Online or Donnelley Financial Solutions have their own CIKs that show up here.
- **Next 2 digits (26):** The filing year (2026).
- **Last 6 digits (004521):** A sequential number assigned by EDGAR.

The accession number is the deduplication key for filing events. No two filings share the same accession number, ever. EFFECT notices use a special CIK prefix (`9999999995`) that identifies them as SEC-generated rather than filer-submitted.

### Constructing EDGAR URLs

The filing index page URL follows a pattern:

```
https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION_NO_DASHES}/{ACCESSION_NUMBER}-index.htm
```

The "no dashes" version removes hyphens from the accession number for the directory path, while the filename retains them.

---

## 8. EDGAR Access Rules

The SEC has explicit rules for programmatic access to EDGAR:

- **Rate limit:** Maximum 10 requests per second. The pipeline enforces a 120ms delay between requests, which gives ~8 req/s with a safety margin.
- **User-Agent required:** Every request must include a User-Agent header with your name and email. The SEC uses this to contact you if your access pattern is problematic. Requests without a proper User-Agent get blocked.
- **No scraping during peak hours:** The SEC asks that automated access avoid peak periods (9:30 AM–10:00 AM ET especially). The pipeline runs against the daily index published around 10 PM ET, so this isn't an issue for daily batch processing.
- **Fair access:** The SEC reserves the right to throttle or block IPs that abuse the system. Staying well under the 10 req/s limit and using polite request headers keeps you in good standing.

---

## 9. How the Pipeline Maps to This Landscape

| Pipeline Component | EDGAR Concept | What It Does |
|-------------------|---------------|--------------|
| `sec/client.py` | Daily index + rate limiting | Downloads `master.YYYYMMDD.idx` files, enforces 120ms request delay, handles weekends/holidays |
| `sec/parsers.py` | Form type filtering + CIK extraction | Parses pipe-delimited index, keeps only monitored form types, extracts accession numbers |
| `pipeline/ingester.py` | Entity resolution + event logging | Matches filings to existing entities by CIK/name, creates new entities only on initial registrations |
| `pipeline/lifecycle.py` | Status advancement | Maps form types to lifecycle stages, advances entity status based on highest-stage filing event |
| `pipeline/notifier.py` | Launch detection | Promotes EFFECTIVE entities to LAUNCHED, inserts into active_securities and notifications |
| `db/operations.py` | CIK-based deduplication | Uses CIK as primary lookup key, accession number for filing event deduplication |

---

## 10. Quick Reference: Filing Type Decision Tree

When a filing comes in from the daily index, the pipeline makes the following decisions:

1. **Is the form type in our monitored set?** If no, skip entirely. If yes, continue.
2. **Does this accession number already exist in filing_events?** If yes, skip (duplicate). If no, continue.
3. **Does this CIK or entity name already exist in our database?** If yes, attach the filing event to the existing entity and advance lifecycle. If no, continue.
4. **Is this an initial registration form (S-1, F-1, N-1A)?** If yes, create a new entity with status FILED. If no, skip — this is a routine filing by an existing issuer not in our pipeline.
