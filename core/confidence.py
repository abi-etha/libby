# core/confidence.py

from typing import List
from core.image_extractor import PageResult


def compute_page_confidence(page: PageResult, vendor: str, end_keywords: List[str]) -> float:
    """
    Compute confidence for a single page.
    Uses PageResult fields instead of old dict-style pages.
    """

    text = page.text or ""
    text_lower = text.lower()

    score = 0.0

    # 1. Text quality
    if len(text) > 50:
        score += 0.2
    if len(text) > 200:
        score += 0.2

    # 2. Vendor keyword presence
    if vendor != "UNKNOWN" and vendor.lower() in text_lower:
        score += 0.2

    # 3. End keyword presence
    if any(k in text_lower for k in end_keywords):
        score += 0.2

    # 4. Page type bonus
    # digital > mixed > scanned
    if page.page_type == "digital":
        score += 0.2
    elif page.page_type == "mixed":
        score += 0.1
    else:
        score += 0.0  # scanned pages get no bonus

    return min(score, 1.0)


def compute_statement_confidence(pages: List[PageResult], vendor: str, end_keywords: List[str], used_fallback: bool) -> float:
    """
    Compute confidence for an entire statement.
    """

    if not pages:
        return 0.0

    total = 0.0
    for page in pages:
        total += compute_page_confidence(page, vendor, end_keywords)

    avg = total / len(pages)

    # Penalty if fallback was used
    if used_fallback:
        avg *= 0.8

    return round(avg, 3)
