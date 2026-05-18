# core/semantic_splitter.py

from core.vendor_fingerprint import VENDORS, detect_vendor
from core.json_logger import JSONLogger
from core.config import LOG_FOLDER

JSON_LOG = JSONLogger(LOG_FOLDER / "events.jsonl")


def semantic_split(pages):
    """
    Splits pages into individual statements.
    Uses start_keywords + end_keywords when defined (e.g. AMEX).
    Falls back to end-keyword-only for other vendors.
    """
    vendor = detect_vendor(pages)
    if vendor is None:
        vendor = "UNKNOWN"

    print(f"SPLITTER: vendor={vendor}, total pages={len(pages)}")

    end_keywords   = VENDORS[vendor]["end_keywords"]
    start_keywords = VENDORS[vendor].get("start_keywords", [])

    statements      = []
    current         = []
    statement_index = 1
    in_statement    = False

    for page in pages:
        text_lower = page.text.lower() if page.text else ""
        has_start  = start_keywords and any(k in text_lower for k in start_keywords)
        has_end    = end_keywords   and any(k in text_lower for k in end_keywords)

        if start_keywords:
            if has_start:
                if current:
                    statements.append((statement_index, current.copy()))
                    statement_index += 1
                current      = [page]
                in_statement = True
            elif in_statement:
                current.append(page)

            if has_end and in_statement:
                statements.append((statement_index, current.copy()))
                statement_index += 1
                current      = []
                in_statement = False
        else:
            current.append(page)
            if vendor != "UNKNOWN" and has_end:
                statements.append((statement_index, current.copy()))
                current = []
                statement_index += 1

    if current:
        statements.append((statement_index, current))

    print(f"SPLITTER: found {len(statements)} statement(s)")
    return vendor, statements
