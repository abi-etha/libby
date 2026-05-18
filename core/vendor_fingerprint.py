# core/vendor_fingerprint.py

import hashlib
from typing import Optional, List
from core.image_extractor import PageResult
from PIL import Image
import io

print("VENDOR FINGERPRINT LOADED")

# IMPORTANT: AMEX must come before CHASE.
# Detection uses scoring across ALL pages so a single
# stray word like "chase" in a transaction line can't win.

VENDORS = {
    "AMEX": {
        "keywords": [
            "american express",
            "americanexpress",
            "amex",
            "americanexpress.com",
            "p.o. box 650448",
            "po box 650448",
            "blue cash",
            "membership rewards",
        ],
        "start_keywords": ["closing date"],
        "end_keywords": [
            "interest charge calculation",
            "days in billing period",
        ],
        "structural_chunk": 4,
        "logo_hashes": [],
    },
    "UFCU": {
        "keywords": [
            "ufcu", "u f c u", "u.f.c.u",
            "university federal credit union",
            "po box 9350", "austin texas 78766", "austin tx 78766",
        ],
        "start_keywords": [],
        "end_keywords": [
            "ytd tax summary",
            "year-to-date information for tax purposes",
            "total non-ira dividends earned",
            "ncua",
        ],
        "structural_chunk": 5,
        "logo_hashes": [],
    },
    "CHASE": {
        "keywords": [
            "chase.com", "jp morgan", "jpmorgan",
            "chase bank", "chase credit card",
            "chase sapphire", "chase freedom",
        ],
        "start_keywords": [],
        "end_keywords": ["ending balance", "deposits and credits"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "TIGER": {
        "keywords": ["tiger sanitation", "tiger disposal"],
        "start_keywords": [],
        "end_keywords": ["amount due", "taxes", "invoice#:"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "SAWS": {
        "keywords": ["san antonio water system", "saws.org"],
        "start_keywords": [],
        "end_keywords": ["mailing address change", "choose a bill payment", "customer service locations"],
        "structural_chunk": 2,
        "logo_hashes": [],
    },
    "ATT": {
        "keywords": ["at&t", "att.com", "att wireless"],
        "start_keywords": [],
        "end_keywords": ["total amount due", "summary of charges"],
        "structural_chunk": 4,
        "logo_hashes": [],
    },
    "SPECTRUM": {
        "keywords": ["spectrum", "charter communications"],
        "start_keywords": [],
        "end_keywords": ["amount due", "service period"],
        "structural_chunk": 1,
        "logo_hashes": [],
    },
    "GMAIL": {
        "keywords": ["gmail", "craigtx.com", "craig@craigtx.com"],
        "start_keywords": [],
        "end_keywords": ["gmail.com", "1/1", "2/2"],
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


def detect_vendor_from_images(page: PageResult) -> Optional[str]:
    for img in page.images:
        img_hash = hash_image_bytes(img["bytes"])
        for vendor, data in VENDORS.items():
            if img_hash in data.get("logo_hashes", []):
                return vendor
    if page.raw_page_image:
        cropped = crop_logo_region(page.raw_page_image)
        crop_hash = hash_image_bytes(cropped)
        for vendor, data in VENDORS.items():
            if crop_hash in data.get("logo_hashes", []):
                return vendor
    return None


def detect_vendor(pages: List[PageResult]) -> Optional[str]:
    """Score-based detection across ALL pages. Most keyword matches wins."""
    if not pages:
        return None

    scores = {v: 0 for v in VENDORS if v != "UNKNOWN"}
    for page in pages:
        if page.text:
            text = page.text.lower()
            for vendor, data in VENDORS.items():
                if vendor == "UNKNOWN":
                    continue
                scores[vendor] += sum(1 for k in data["keywords"] if k in text)

    best_vendor = max(scores, key=scores.get)
    if scores[best_vendor] > 0:
        print(f"VENDOR DETECTION: {best_vendor} (score={scores[best_vendor]}) | all: {scores}")
        return best_vendor

    for page in pages:
        vendor = detect_vendor_from_images(page)
        if vendor:
            return vendor

    return None
