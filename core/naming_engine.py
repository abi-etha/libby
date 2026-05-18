# core/naming_engine.py

import re
from datetime import datetime
from core.vendor_fingerprint import VENDORS

DATE_PATTERNS = [
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}",
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}",
    r"\d{1,2}/\d{1,2}/\d{4}",
    r"\d{4}-\d{2}-\d{2}",
    r"\d{4}-\d{2}",
]

VENDOR_DATE_PATTERNS = {
    "AMEX": [
        r"closing date\s+(\d{1,2}/\d{1,2}/\d{2,4})",
    ],
}


def normalize_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%B %d, %Y", "%b %Y", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m")
        except Exception:
            pass
    return "unknown"


def extract_date(text: str, vendor: str = None) -> str:
    text_lower = text.lower()

    if vendor and vendor in VENDOR_DATE_PATTERNS:
        for pattern in VENDOR_DATE_PATTERNS[vendor]:
            match = re.search(pattern, text_lower)
            if match:
                normalized = normalize_date(match.group(1))
                if normalized != "unknown":
                    print(f"DATE: '{match.group(1)}' → {normalized} (vendor pattern)")
                    return normalized

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            normalized = normalize_date(match.group())
            if normalized != "unknown":
                print(f"DATE: '{match.group()}' → {normalized} (global pattern)")
                return normalized

    print("DATE: not found")
    return "unknown"


def build_filename(prefix: str, vendor: str, date: str, index: int, confidence: float = None) -> str:
    vendor_clean = vendor.replace(" ", "").upper()
    date_clean   = date if date != "unknown" else "0000-00"
    confidence_suffix = ""
    if confidence is not None and confidence < 0.5:
        confidence_suffix = f"_lowconf_{int(confidence * 100)}"
    return f"{prefix}_{vendor_clean}_{date_clean}_statement_{index:03d}{confidence_suffix}.pdf"
