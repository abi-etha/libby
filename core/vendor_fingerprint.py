import re
import csv
import hashlib
from pathlib import Path
from typing import Optional, List, Dict
from core.image_extractor import PageResult
from PIL import Image
import io

# ── Load vendors from CSV ──────────────────────────────────────────────────

def _load_vendors(csv_path: Path) -> Dict:
    """
    Load vendor definitions from vendors.csv.
    Falls back to empty MISC-only dict if file is missing.
    """
    vendors = {}
    if not csv_path.exists():
        print(f"WARNING: vendors.csv not found at {csv_path}")
        vendors["MISC"] = {
            "keywords": [], "start_keywords": [], "end_keywords": [],
            "structural_chunk": 1, "logo_hashes": [],
        }
        vendors["UNKNOWN"] = {
            "keywords": [], "start_keywords": [], "end_keywords": [],
            "structural_chunk": 1, "logo_hashes": [],
        }
        return vendors

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor = row["vendor"].strip().upper()
            vendors[vendor] = {
                "keywords":        [k.strip() for k in row["keywords"].split(";") if k.strip()],
                "start_keywords":  [k.strip() for k in row["start_keywords"].split(";") if k.strip()],
                "end_keywords":    [k.strip() for k in row["end_keywords"].split(";") if k.strip()],
                "structural_chunk": int(row["structural_chunk"]) if row["structural_chunk"].strip() else 1,
                "logo_hashes":     [],
            }

    # Always ensure UNKNOWN exists
    if "UNKNOWN" not in vendors:
        vendors["UNKNOWN"] = {
            "keywords": [], "start_keywords": [], "end_keywords": [],
            "structural_chunk": 1, "logo_hashes": [],
        }

    print(f"VENDOR FINGERPRINT LOADED: {len(vendors)} vendors from {csv_path.name}")
    return vendors


# Load at module import time — path relative to this file's parent (project root)
_VENDORS_CSV = Path(__file__).parent.parent / "vendors.csv"
VENDORS = _load_vendors(_VENDORS_CSV)


# ── Detection ──────────────────────────────────────────────────────────────

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
    Header (before first date) and footer (last 300 chars) score 5x over body.
    Returns vendor name or None if no match.
    """
    if not page.text:
        return _detect_from_images(page)

    text = page.text
    n = len(text)

    # Find where the transaction table starts (first MM/DD/YYYY date)
    date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text)
    header_end = date_match.start() if date_match else min(500, n)

    header = text[:header_end].lower()
    footer = text[max(0, n - 300):].lower()
    body   = text[header_end:max(0, n - 300)].lower()

    scores = {v: 0 for v in VENDORS if v not in ("UNKNOWN", "MISC")}

    for vendor, data in VENDORS.items():
        if vendor in ("UNKNOWN", "MISC"):
            continue
        for keyword in data["keywords"]:
            if keyword in header:
                scores[vendor] += 5
            if keyword in footer:
                scores[vendor] += 5
            if keyword in body:
                scores[vendor] += 1

    best = max(scores, key=scores.get) if scores else None
    if best and scores[best] > 0:
        return best

    return _detect_from_images(page)


def _detect_from_images(page: PageResult) -> Optional[str]:
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
    """Legacy: score across ALL pages. Kept for backward compatibility."""
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

    best = max(scores, key=scores.get) if scores else None
    if best and scores[best] > 0:
        print(f"VENDOR DETECTION: {best} (score={scores[best]}) | all: {scores}")
        return best

    for page in pages:
        vendor = _detect_from_images(page)
        if vendor:
            return vendor

    return None
