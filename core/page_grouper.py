# core/page_grouper.py
#
# Replaces semantic_splitter.py + consolidator.py
#
# Strategy:
#   1. Classify every page by doc type
#   2. Detect vendor per page
#   3. Extract date per page
#   4. Group pages by (vendor, doc_type, year-month)
#   5. Sort pages within each group by printed page number
#   6. Return clean list of groups ready for output

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from core.image_extractor import PageResult
from core.page_classifier import classify_page, majority_doc_type
from core.vendor_fingerprint import VENDORS, detect_vendor_for_page

# ── Date extraction ────────────────────────────────────────────────────────

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

DATE_PATTERNS = [
    # "January 31, 2025" or "Jan 31, 2025"
    (re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(\d{4})", re.IGNORECASE), "month_day_year"),
    # "January 2025" or "Jan 2025"
    (re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})", re.IGNORECASE), "month_year"),
    # "01/31/2025" or "01/31/25"
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b"), "mdy"),
    # "2025-01-31" or "2025-01"
    (re.compile(r"\b(\d{4})-(\d{2})(?:-\d{2})?\b"), "iso"),
    # "statement period" or "billing period" followed by date
    (re.compile(r"(?:statement|billing)\s+period[:\s]+.*?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(\d{4})", re.IGNORECASE), "period_month_day_year"),
]

# Anchor phrases that indicate the date that follows is the statement date
DATE_ANCHOR_PATTERNS = [
    re.compile(r"(?:closing date|statement date|billing date|period ending|as of|through|thru)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})", re.IGNORECASE),
    re.compile(r"(?:closing date|statement date|billing date|period ending|as of|through|thru)[:\s]+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})", re.IGNORECASE),
]


def extract_year_month(text: str) -> Optional[str]:
    """
    Extract the best year-month string (YYYY-MM) from page text.
    Tries anchor patterns first, then general patterns.
    Returns None if no date found.
    """
    if not text:
        return None

    # Try anchored patterns first (most reliable)
    for pattern in DATE_ANCHOR_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1)
            result = _parse_date_to_ym(raw)
            if result:
                return result

    # Try general patterns
    for pattern, kind in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        try:
            if kind == "month_day_year" or kind == "period_month_day_year":
                month_str = match.group(1)[:3].lower()
                year = match.group(2) if kind == "month_day_year" else match.group(2)
                month = MONTH_MAP.get(month_str)
                if month and year:
                    return f"{year}-{month}"

            elif kind == "month_year":
                month_str = match.group(1)[:3].lower()
                year = match.group(2)
                month = MONTH_MAP.get(month_str)
                if month and year:
                    return f"{year}-{month}"

            elif kind == "mdy":
                month = match.group(1).zfill(2)
                year = match.group(3)
                if len(year) == 2:
                    year = "20" + year
                if int(year) >= 2000:
                    return f"{year}-{month}"

            elif kind == "iso":
                year = match.group(1)
                month = match.group(2)
                if int(year) >= 2000:
                    return f"{year}-{month}"

        except Exception:
            continue

    return None


def _parse_date_to_ym(raw: str) -> Optional[str]:
    """Parse a raw date string to YYYY-MM."""
    raw = raw.strip()

    # MM/DD/YYYY or MM/DD/YY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw)
    if m:
        month = m.group(1).zfill(2)
        year = m.group(3)
        if len(year) == 2:
            year = "20" + year
        return f"{year}-{month}"

    # "Jan 31, 2025" etc
    m = re.match(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(\d{4})", raw, re.IGNORECASE)
    if m:
        month = MONTH_MAP.get(m.group(1)[:3].lower())
        year = m.group(2)
        if month:
            return f"{year}-{month}"

    return None


# ── Page number extraction ─────────────────────────────────────────────────

PAGE_NUM_PATTERNS = [
    re.compile(r"p\.?\s*(\d+)\s*/\s*(\d+)"),     # p. 1/8  or  p.1/8
    re.compile(r"page\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE),  # page 1 of 8
    re.compile(r"page\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE),   # page 1/8
]


def extract_printed_page_number(text: str) -> Tuple[int, int]:
    """Returns (current, total) or (0, 0) if not found."""
    snippet = (text or "")[:500]
    for pattern in PAGE_NUM_PATTERNS:
        m = pattern.search(snippet)
        if m:
            try:
                return int(m.group(1)), int(m.group(2))
            except Exception:
                pass
    return 0, 0


# ── Group key ─────────────────────────────────────────────────────────────

@dataclass
class PageGroup:
    vendor: str
    doc_type: str
    year_month: str          # "YYYY-MM" or "unknown"
    pages: List[PageResult]

    @property
    def key(self) -> str:
        return f"{self.vendor}|{self.doc_type}|{self.year_month}"


# ── Main grouper ──────────────────────────────────────────────────────────

def group_pages(pages: List[PageResult]) -> List[PageGroup]:
    """
    Main entry point. Takes a flat list of pages (from one or more PDFs)
    and returns a list of PageGroups — one per logical statement.
    """

    if not pages:
        return []

    # ── Step 1: Classify + detect vendor + extract date per page ──────────
    page_meta = []
    for page in pages:
        doc_type  = classify_page(page)
        vendor    = detect_vendor_for_page(page)
        year_month = extract_year_month(page.text or "")
        page_meta.append({
            "page":       page,
            "doc_type":   doc_type,
            "vendor":     vendor,
            "year_month": year_month,
        })
        print(f"  PAGE {page.page_number}: type={doc_type}, vendor={vendor}, date={year_month}")

    # ── Step 2: Resolve unknowns by propagating from neighbors ────────────
    page_meta = _propagate_metadata(page_meta)

    # ── Step 3: Group by (vendor, doc_type, year_month) ──────────────────
    groups: Dict[str, List[PageResult]] = {}
    group_meta: Dict[str, Dict] = {}

    for meta in page_meta:
        vendor     = meta["vendor"] or "MISC"
        doc_type   = meta["doc_type"] or "other"
        year_month = meta["year_month"] or "unknown"
        key        = f"{vendor}|{doc_type}|{year_month}"

        if key not in groups:
            groups[key] = []
            group_meta[key] = {"vendor": vendor, "doc_type": doc_type, "year_month": year_month}

        groups[key].append(meta["page"])

    # ── Step 4: Sort pages within each group ─────────────────────────────
    result = []
    for key, group_pages in sorted(groups.items()):
        sorted_pages = _sort_pages(group_pages)
        meta = group_meta[key]
        result.append(PageGroup(
            vendor=meta["vendor"],
            doc_type=meta["doc_type"],
            year_month=meta["year_month"],
            pages=sorted_pages,
        ))
        print(f"GROUP: {key} → {len(sorted_pages)} pages")

    return result


def _propagate_metadata(page_meta: List[Dict]) -> List[Dict]:
    """
    Fill in missing vendor/doc_type/year_month from neighboring pages.

    Key rule: a page with NO DATE is almost always a continuation of the
    previous page (e.g. a summary/footer page). Forward-fill is the primary
    strategy. Backward-fill only handles the edge case where the first page(s)
    have no metadata.

    Vendor and doc_type are always forward-filled since they rarely change
    within a single PDF.
    """
    n = len(page_meta)

    # ── Pass 1: Forward fill everything ───────────────────────────────────
    last_vendor     = None
    last_doc_type   = None
    last_year_month = None

    for i in range(n):
        m = page_meta[i]

        # Vendor: always forward-fill — institution name rarely appears on
        # continuation pages, but transaction lines do (and score low now)
        if m["vendor"]:
            last_vendor = m["vendor"]
        if not m["vendor"] and last_vendor:
            m["vendor"] = last_vendor

        # Doc type: forward-fill, ignore "other" as a signal
        if m["doc_type"] and m["doc_type"] != "other":
            last_doc_type = m["doc_type"]
        if (not m["doc_type"] or m["doc_type"] == "other") and last_doc_type:
            m["doc_type"] = last_doc_type

        # Year-month: forward-fill — summary/footer pages have no date header
        # so they should inherit the month from the page before them
        if m["year_month"]:
            last_year_month = m["year_month"]
        if not m["year_month"] and last_year_month:
            m["year_month"] = last_year_month

    # ── Pass 2: Backward fill for pages before first identified page ──────
    last_vendor     = None
    last_doc_type   = None
    last_year_month = None

    for i in range(n - 1, -1, -1):
        m = page_meta[i]

        if m["vendor"]:
            last_vendor = m["vendor"]
        if not m["vendor"] and last_vendor:
            m["vendor"] = last_vendor

        if m["doc_type"] and m["doc_type"] != "other":
            last_doc_type = m["doc_type"]
        if (not m["doc_type"] or m["doc_type"] == "other") and last_doc_type:
            m["doc_type"] = last_doc_type

        if m["year_month"]:
            last_year_month = m["year_month"]
        if not m["year_month"] and last_year_month:
            m["year_month"] = last_year_month

    return page_meta


def _sort_pages(pages: List[PageResult]) -> List[PageResult]:
    """Sort pages by printed page number, falling back to PDF page order."""
    def sort_key(page: PageResult):
        current, total = extract_printed_page_number(page.text or "")
        if current > 0:
            return (0, current)
        return (1, page.page_number)

    return sorted(pages, key=sort_key)
