"""LLM enrichment for N-1A filings.

Fetches the primary prospectus document from EDGAR, strips it to plain text, and
calls an OpenAI-compatible API to extract structured fund metadata (investment
theme, expense ratio, portfolio manager, etc.). The set of fields is driven by
``config.N1A_ENRICHMENT_FIELDS`` so adding a new field is a one-line change
there + a column in ``db/models.py``.

Any field the LLM cannot find is left as ``None`` so the DB column stays NULL.
"""

import json
import logging
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from openai import OpenAI

from config import (
    LLM_API_BASE_URL,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_MAX_DOC_CHARS,
    N1A_ENRICHMENT_FIELDS,
)
from sec.client import EdgarClient

logger = logging.getLogger(__name__)

# Documents we consider "the prospectus" — N-1A filings include exhibits, XML
# headers, image files, etc., and we only want the human-readable narrative.
_PRIMARY_DOC_EXTENSIONS = (".htm", ".html", ".txt")
_SKIP_FILENAME_HINTS = ("exhibit", "ex-", "ex_", "ex99", "cover", "xml", "r1.htm", "filingsummary")


def _build_openai_client() -> OpenAI:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is empty. Set LLM_API_KEY in .env to enable enrichment."
        )
    kwargs: dict[str, Any] = {"api_key": LLM_API_KEY}
    if LLM_API_BASE_URL:
        kwargs["base_url"] = LLM_API_BASE_URL
    return OpenAI(**kwargs)


def _pick_primary_document(index_json: dict) -> str | None:
    """From a filing's index.json, return the filename of the primary prospectus doc.

    Heuristic: among .htm/.html/.txt items that don't look like exhibits or
    boilerplate, pick the largest by size — that's almost always the prospectus.
    """
    items = index_json.get("directory", {}).get("item", [])
    candidates = []
    for it in items:
        name = (it.get("name") or "").lower()
        if not name.endswith(_PRIMARY_DOC_EXTENSIONS):
            continue
        if any(hint in name for hint in _SKIP_FILENAME_HINTS):
            continue
        # The full submission txt file (named like 0001234567-24-000123.txt) is
        # SGML-wrapped; skip it in favor of the standalone HTML.
        if name.endswith(".txt") and name.count("-") >= 2:
            continue
        try:
            size = int(it.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        candidates.append((size, it.get("name")))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse runs of blank lines that .htm prospectuses are full of.
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def fetch_n1a_text(cik: str, accession_number: str, client: EdgarClient | None = None) -> str | None:
    """Fetch and extract plain-text content of the primary doc in an N-1A filing."""
    if not cik or not accession_number:
        logger.warning("fetch_n1a_text: missing cik or accession_number")
        return None

    client = client or EdgarClient()
    try:
        index_json = client.fetch_filing_index_json(cik, accession_number)
    except Exception as e:
        logger.warning("Failed to fetch index.json for %s/%s: %s", cik, accession_number, e)
        return None

    primary = _pick_primary_document(index_json)
    if not primary:
        logger.warning("No primary document found in filing %s/%s", cik, accession_number)
        return None

    try:
        raw = client.fetch_filing_document(cik, accession_number, primary)
    except Exception as e:
        logger.warning("Failed to fetch %s for %s/%s: %s", primary, cik, accession_number, e)
        return None

    if primary.lower().endswith((".htm", ".html")):
        return _html_to_text(raw)
    return raw


def _build_extraction_prompt(doc_text: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the extraction call."""
    field_lines = "\n".join(
        f'  - "{name}": {desc}' for name, desc in N1A_ENRICHMENT_FIELDS.items()
    )
    json_keys = ", ".join(f'"{k}"' for k in N1A_ENRICHMENT_FIELDS)

    system = (
        "You extract structured metadata from SEC Form N-1A registration "
        "statements (mutual fund / ETF prospectuses). Reply with a single JSON "
        "object and nothing else. For any field whose value is not clearly stated "
        "in the document, use null. Do not guess. expense_ratio must be a decimal "
        "number (e.g. 0.0075 for 0.75%) or null."
    )

    user = (
        "Extract the following fields from the N-1A filing text below.\n\n"
        f"Fields:\n{field_lines}\n\n"
        f"Reply with a JSON object using exactly these keys: {json_keys}.\n"
        "Use null for any field you cannot find verbatim in the text.\n\n"
        "--- N-1A FILING TEXT ---\n"
        f"{doc_text}\n"
        "--- END FILING TEXT ---"
    )
    return system, user


def _coerce_value(field: str, value: Any) -> Any:
    """Light type cleanup. Most fields stay strings; expense_ratio becomes float."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ("", "null", "none", "n/a", "not specified"):
        return None
    if field == "expense_ratio":
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "")
            try:
                f = float(cleaned)
            except ValueError:
                return None
            # If the LLM returned 0.75 instead of 0.0075, normalize down.
            if f > 1:
                f = f / 100.0
            return f
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def extract_fields_from_text(
    doc_text: str,
    *,
    model: str | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Call the LLM on N-1A text and return a dict keyed by N1A_ENRICHMENT_FIELDS.

    Any field not found is set to None. Raises if the API call fails — callers
    should catch and log so a single bad enrichment doesn't kill ingestion.
    """
    max_chars = max_chars or LLM_MAX_DOC_CHARS
    if len(doc_text) > max_chars:
        logger.info("Truncating N-1A text from %d to %d chars", len(doc_text), max_chars)
        doc_text = doc_text[:max_chars]

    system, user = _build_extraction_prompt(doc_text)
    client = _build_openai_client()

    resp = client.chat.completions.create(
        model=model or LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON content; treating all fields as null. Raw: %r", raw[:200])
        parsed = {}

    result = {}
    for field in N1A_ENRICHMENT_FIELDS:
        result[field] = _coerce_value(field, parsed.get(field))
    return result


def enrich_n1a(cik: str, accession_number: str, client: EdgarClient | None = None) -> dict[str, Any] | None:
    """End-to-end: fetch N-1A doc, run LLM extraction, return field dict (or None on failure)."""
    text = fetch_n1a_text(cik, accession_number, client=client)
    if not text:
        return None
    try:
        fields = extract_fields_from_text(text)
    except Exception as e:
        logger.warning("LLM extraction failed for %s/%s: %s", cik, accession_number, e)
        return None
    fields["enriched_at"] = datetime.utcnow().isoformat()
    logger.info(
        "Enriched %s/%s: populated %d/%d fields",
        cik,
        accession_number,
        sum(1 for k, v in fields.items() if k != "enriched_at" and v is not None),
        len(N1A_ENRICHMENT_FIELDS),
    )
    return fields
