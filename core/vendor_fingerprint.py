# core/vendor_fingerprint.py
#
# Vendor detection — expanded list, per-page scoring.

import hashlib
from typing import Optional, List
from core.image_extractor import PageResult
from PIL import Image
import io

print("VENDOR FINGERPRINT LOADED")

VENDORS = {
    # ── Banks ──────────────────────────────────────────────────────────────
    "BOA": {
        "keywords": ["bank of america", "bankofamerica", "boa", "merrill lynch"],
        "start_keywords": [],
        "end_keywords": ["ending balance", "total deposits", "total withdrawals"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "CHASE": {
        "keywords": ["chase.com", "jp morgan", "jpmorgan", "chase bank", "chase credit card", "chase sapphire", "chase freedom"],
        "start_keywords": [],
        "end_keywords": ["ending balance", "deposits and credits"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "WELLS": {
        "keywords": ["wells fargo", "wellsfargo", "wf bank"],
        "start_keywords": [],
        "end_keywords": ["ending balance", "total deposits", "total withdrawals"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "USAA": {
        "keywords": ["usaa", "usaa federal savings bank", "usaa.com"],
        "start_keywords": [],
        "end_keywords": ["ending balance", "deposits", "withdrawals"],
        "structural_chunk": 5,
        "logo_hashes": [],
    },
    "UFCU": {
        "keywords": ["ufcu", "u f c u", "u.f.c.u", "university federal credit union", "po box 9350", "austin texas 78766"],
        "start_keywords": [],
        "end_keywords": ["ytd tax summary", "year-to-date information for tax purposes", "ncua"],
        "structural_chunk": 5,
        "logo_hashes": [],
    },
    "FIRSTNATIONAL": {
        "keywords": ["first national bank", "firstnationaltx", "fnb"],
        "start_keywords": ["opening balance"],
        "end_keywords": ["closing balance", "total credits", "total debits"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "CITI": {
        "keywords": ["citibank", "citi card", "citi.com", "citicards"],
        "start_keywords": [],
        "end_keywords": ["new balance", "payment due", "closing date"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "CAPONE": {
        "keywords": ["capital one", "capitalone.com", "cap one"],
        "start_keywords": [],
        "end_keywords": ["new balance", "payment due", "closing date"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },

    # ── Credit Cards ───────────────────────────────────────────────────────
    "AMEX": {
        "keywords": ["american express", "americanexpress", "amex", "americanexpress.com", "p.o. box 650448", "blue cash", "membership rewards"],
        "start_keywords": ["closing date"],
        "end_keywords": ["interest charge calculation", "days in billing period"],
        "structural_chunk": 4,
        "logo_hashes": [],
    },
    "DISCOVER": {
        "keywords": ["discover", "discover card", "discover bank", "discover.com"],
        "start_keywords": [],
        "end_keywords": ["new balance", "payment due", "closing date"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "PAYPAL": {
        "keywords": ["paypal", "pp credit", "paypal credit", "paypal.com"],
        "start_keywords": [],
        "end_keywords": ["new balance", "payment due", "closing date"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
    "AMAZON": {
        "keywords": ["amazon", "amazon card", "amazon visa", "amazon.com"],
        "start_keywords": [],
        "end_keywords": ["new balance", "payment due", "closing date"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },

    # ── Utilities ──────────────────────────────────────────────────────────
    "ATT": {
        "keywords": ["at&t", "att.com", "att wireless", "at&t mobility"],
        "start_keywords": [],
        "end_keywords": ["total amount due", "summary of charges"],
        "structural_chunk": 4,
        "logo_hashes": [],
    },
    "SPECTRUM": {
        "keywords": ["spectrum", "charter communications", "spectrum.net"],
        "start_keywords": [],
        "end_keywords": ["amount due", "service period"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
    "SAWS": {
        "keywords": ["san antonio water system", "saws.org", "saws"],
        "start_keywords": [],
        "end_keywords": ["mailing address change", "choose a bill payment", "customer service locations"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "CPS": {
        "keywords": ["cps energy", "cpsenergy.com", "city public service"],
        "start_keywords": [],
        "end_keywords": ["amount due", "total due", "billing summary"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "COMED": {
        "keywords": ["comed", "electric service", "commonwealth edison"],
        "start_keywords": [],
        "end_keywords": ["total amount due", "billing summary"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "VERIZON": {
        "keywords": ["verizon", "verizon wireless", "vzw", "verizon.com"],
        "start_keywords": [],
        "end_keywords": ["total amount due", "account summary"],
        "structural_chunk": 3,
        "logo_hashes": [],
    },
    "TMOBILE": {
        "keywords": ["t-mobile", "tmobile", "t mobile", "t-mobile.com"],
        "start_keywords": [],
        "end_keywords": ["total amount due", "account summary"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },

    # ── Services ───────────────────────────────────────────────────────────
    "TIGER": {
        "keywords": ["tiger sanitation", "tiger disposal"],
        "start_keywords": [],
        "end_keywords": ["amount due", "taxes", "invoice#:"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "UPS": {
        "keywords": ["ups", "united parcel service", "ups.com"],
        "start_keywords": [],
        "end_keywords": ["tracking summary", "billing summary", "charges"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
    "FEDEX": {
        "keywords": ["fedex", "federal express", "fedex.com"],
        "start_keywords": [],
        "end_keywords": ["charges", "billing summary", "invoice total"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
    "GMAIL": {
        "keywords": ["gmail", "craigtx.com"],
        "start_keywords": [],
        "end_keywords": ["gmail.com", "1/1", "2/2"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },

    # ── Fallback ───────────────────────────────────────────────────────────
    "MISC": {
        "keywords": [],
        "start_keywords": [],
        "end_keywords": [],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
    "UNKNOWN": {
        "keywords": [],
        "start_keywords": [],
        "end_keywords": [],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
}


def hash_image_bytes(image_bytes: bytes) -> str:
    return hashlib.sha1(image_bytes).hexdigest()


def crop_logo_region(raw_bytes: bytes, box=(0, 0, 300, 150)):
    img = Image.open(io.BytesIO(raw_bytes))
    cropped = img.crop(box)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def detect_vendor_for_page(page: PageResult) -> Optional[str]:
    """
    Score-based vendor detection for a single page.
    Weights header (first 500 chars) and footer (last 300 chars) 5x more
    than body text, so institution names beat merchant names in transactions.
    Returns vendor name or None if no match.
    """
    if not page.text:
        return _detect_from_images(page)

    text = page.text
    n = len(text)

    # Split into zones with different weights
    header = text[:min(500, n)].lower()
    footer = text[max(0, n - 300):].lower()
    body   = text[min(500, n):max(0, n - 300)].lower()

    scores = {v: 0 for v in VENDORS if v not in ("UNKNOWN", "MISC")}

    for vendor, data in VENDORS.items():
        if vendor in ("UNKNOWN", "MISC"):
            continue
        for keyword in data["keywords"]:
            if keyword in header:
                scores[vendor] += 5   # header hit — strong signal
            if keyword in footer:
                scores[vendor] += 5   # footer hit — strong signal
            if keyword in body:
                scores[vendor] += 1   # body hit — weak signal (could be a transaction)

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best

    return _detect_from_images(page)


def _detect_from_images(page: PageResult) -> Optional[str]:
    """Image hash based vendor detection."""
    for img in (page.images or []):
        img_hash = hash_image_bytes(img["bytes"])
        for vendor, data in VENDORS.items():
            if img_hash in data.get("logo_hashes", []):
                return vendor

    if page.raw_page_image:
        try:
            cropped = crop_logo_region(page.raw_page_image)
            crop_hash = hash_image_bytes(cropped)
            for vendor, data in VENDORS.items():
                if crop_hash in data.get("logo_hashes", []):
                    return vendor
        except Exception:
            pass

    return None


def detect_vendor(pages: List[PageResult]) -> Optional[str]:
    """
    Legacy: score-based detection across ALL pages. Used by old splitter.
    Kept for backward compatibility.
    """
    if not pages:
        return None

    scores = {v: 0 for v in VENDORS if v not in ("UNKNOWN", "MISC")}
    for page in pages:
        if page.text:
            text = page.text.lower()
            for vendor, data in VENDORS.items():
                if vendor in ("UNKNOWN", "MISC"):
                    continue
                scores[vendor] += sum(1 for k in data["keywords"] if k in text)

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        print(f"VENDOR DETECTION: {best} (score={scores[best]}) | all: {scores}")
        return best

    for page in pages:
        vendor = _detect_from_images(page)
        if vendor:
            return vendor

    return None
