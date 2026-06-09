# core/statement_router.py
#
# Main pipeline orchestrator — updated to use new page grouper.

from core.pdf_loader import load_pdf
from core.page_grouper import group_pages
from core.page_classifier import needs_csv, majority_doc_type
from core.naming_engine import build_filename, build_csv_filename
from core.confidence import compute_statement_confidence
from core.transaction_extractor import extract_transactions, transactions_to_csv
from core.vendor_fingerprint import VENDORS
from core.json_logger import JSONLogger
from core.config import LOG_FOLDER

JSON_LOG = JSONLogger(LOG_FOLDER / "events.jsonl")


def process_pdf(path: str, prefix: str):
    """
    Full pipeline:
      1. Load pages from PDF
      2. Classify each page (doc type + vendor + date)
      3. Group pages into logical statements
      4. Extract transactions for bank/credit statements
      5. Build filenames, score confidence, return results
    """

    # 1. Load
    pages = load_pdf(path)
    if not pages:
        print("ERROR: No pages loaded")
        return []

    print(f"\nLOADED: {len(pages)} pages from {path}\n")

    # 2 & 3. Classify + group
    groups = group_pages(pages)

    if not groups:
        print("ERROR: No statement groups found")
        return []

    print(f"\nFOUND: {len(groups)} statement group(s)\n")

    # 4. Build results — index resets per unique vendor+doctype+month combo
    results = []
    index_counters = {}  # key -> count

    for group in groups:
        vendor     = group.vendor or "MISC"
        doc_type   = group.doc_type or "other"
        year_month = group.year_month or "unknown"
        pages_list = group.pages

        # Get end_keywords for confidence scoring
        vendor_data  = VENDORS.get(vendor, VENDORS["MISC"])
        end_keywords = vendor_data.get("end_keywords", [])

        confidence = compute_statement_confidence(
            pages_list, vendor, end_keywords, used_fallback=False
        )

        # Per-group counter — resets for each unique statement key
        group_key = f"{vendor}|{doc_type}|{year_month}"
        index_counters[group_key] = index_counters.get(group_key, 0) + 1
        index = index_counters[group_key]

        filename     = build_filename(prefix, vendor, doc_type, year_month, index, confidence)
        csv_filename = build_csv_filename(filename)

        # Extract transactions only for bank/credit statements
        transactions = []
        csv_content  = ""
        if needs_csv(doc_type):
            transactions = extract_transactions(pages_list, vendor, year_month)
            csv_content  = transactions_to_csv(transactions, vendor)

        JSON_LOG.log_statement_result(
            pdf_path=path,
            filename=filename,
            vendor=vendor,
            date=year_month,
            index=index,
            confidence=confidence,
            used_fallback=False,
        )

        results.append({
            "filename":      filename,
            "csv_filename":  csv_filename,
            "csv_content":   csv_content,
            "vendor":        vendor,
            "doc_type":      doc_type,
            "date":          year_month,
            "index":         index,
            "confidence":    confidence,
            "used_fallback": False,
            "pages":         pages_list,
            "transactions":  len(transactions),
        })

        print(f"  → {filename} ({len(pages_list)} pages, {len(transactions)} transactions, confidence={confidence:.2f})")

    return results
