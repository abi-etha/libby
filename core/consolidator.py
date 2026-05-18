# core/consolidator.py
#
# After the splitter runs, we may have fragments:
#   - Page 1 of Jan alone (1 page)
#   - Pages 2-4 of Jan (3 pages)
#   - A stray March page sitting in November's group
#
# This module:
#   1. Groups all statement fragments by vendor + date
#   2. Within each group, sorts pages by their printed page number
#      (AMEX prints "p. 1/8", "p. 2/8" etc. in the top-right corner)
#   3. Merges them into one clean ordered statement per date

import re
from typing import List, Tuple, Dict
from core.image_extractor import PageResult


# ── Page number extraction ─────────────────────────────────────────────────

# Matches: "p. 1/8", "p.1/8", "p 1/8", "page 1/8", "1/8" near top of page
PAGE_NUM_PATTERNS = [
    r"p\.\s*(\d+)/(\d+)",          # p. 1/8  or  p.1/8
    r"p\s+(\d+)/(\d+)",            # p 1/8
    r"page\s+(\d+)\s*/\s*(\d+)",   # page 1/8  or  page 1 / 8
]


def extract_page_number(text: str) -> Tuple[int, int]:
    """
    Returns (current_page, total_pages) from printed page markers.
    Returns (0, 0) if not found.
    """
    # Only look at the first 300 characters — the marker is always near the top
    snippet = text[:300] if text else ""

    for pattern in PAGE_NUM_PATTERNS:
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match:
            try:
                current = int(match.group(1))
                total   = int(match.group(2))
                return current, total
            except Exception:
                pass

    return 0, 0


# ── Consolidation ──────────────────────────────────────────────────────────

def consolidate_statements(
    statements: List[Tuple[int, List[PageResult]]],
    vendor: str,
    dates: Dict[int, str],          # index → date string
) -> List[Tuple[str, List[PageResult]]]:
    """
    Takes the raw list of (index, pages) from the splitter and:
    1. Groups fragments that share the same date
    2. Sorts pages within each group by printed page number
    3. Returns list of (date, sorted_pages) — one entry per unique statement

    Fragments with unknown dates are kept as-is in their original order.
    """

    # ── Group by date ──────────────────────────────────────────────────────
    date_groups: Dict[str, List[PageResult]] = {}
    unknown_groups: List[Tuple[int, List[PageResult]]] = []

    for index, pages in statements:
        date = dates.get(index, "unknown")
        if date == "unknown":
            unknown_groups.append((index, pages))
        else:
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].extend(pages)

    # ── Sort pages within each date group ──────────────────────────────────
    results = []

    for date, pages in sorted(date_groups.items()):
        # Try to sort by printed page number
        def sort_key(page: PageResult):
            current, total = extract_page_number(page.text or "")
            if current > 0:
                return current
            # Fall back to original PDF page order
            return page.page_number

        sorted_pages = sorted(pages, key=sort_key)

        # Log what we found
        page_nums = []
        for p in sorted_pages:
            cur, tot = extract_page_number(p.text or "")
            page_nums.append(f"p.{cur}/{tot}" if cur > 0 else f"pdf#{p.page_number}")
        print(f"CONSOLIDATE: {vendor} {date} — {len(sorted_pages)} pages: {page_nums}")

        results.append((date, sorted_pages))

    # ── Append unknowns at the end ─────────────────────────────────────────
    for index, pages in unknown_groups:
        print(f"CONSOLIDATE: unknown date fragment, {len(pages)} pages kept as-is")
        results.append(("unknown", pages))

    return results
