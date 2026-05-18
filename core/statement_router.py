# core/statement_router.py

from core.pdf_loader import load_pdf
from core.semantic_splitter import semantic_split
from core.structural_fallback import structural_split
from core.naming_engine import extract_date, build_filename
from core.confidence import compute_statement_confidence
from core.consolidator import consolidate_statements
from core.transaction_extractor import extract_transactions, transactions_to_csv
from core.vendor_fingerprint import VENDORS
from core.json_logger import JSONLogger
from core.config import LOG_FOLDER

JSON_LOG = JSONLogger(LOG_FOLDER / "events.jsonl")


def process_pdf(path: str, prefix: str):
    """
    Full pipeline:
      1. Load pages
      2. Detect vendor + split into statement fragments
      3. Extract date from each fragment
      4. Consolidate fragments by date, sort pages by printed page number
      5. Extract transactions → CSV
      6. Build filenames, score confidence, return results
    """

    # 1. Load
    pages = load_pdf(path)
    if not pages:
        print("ERROR: No pages loaded")
        return []

    print(f"\nLOADED: {len(pages)} pages from {path}\n")

    # 2. Split
    try:
        vendor, statements = semantic_split(pages)
        used_fallback = False
    except Exception as e:
        print("Semantic split failed:", e)
        vendor = "UNKNOWN"
        statements = structural_split(pages, vendor=vendor)
        used_fallback = True

    print(f"SPLIT: {len(statements)} fragment(s) for vendor={vendor}")

    # 3. Extract date from each fragment
    dates = {}
    for index, statement_pages in statements:
        date = "unknown"
        for page in statement_pages:
            date = extract_date(page.text or "", vendor)
            if date != "unknown":
                break
        dates[index] = date
        print(f"  Fragment {index}: {len(statement_pages)} pages, date={date}")

    # 4. Consolidate
    consolidated = consolidate_statements(statements, vendor, dates)
    print(f"CONSOLIDATED: {len(consolidated)} final statement(s)")

    # 5. Build results
    results = []
    end_keywords = VENDORS[vendor]["end_keywords"]

    for final_index, (date, statement_pages) in enumerate(consolidated, start=1):
        filename     = build_filename(prefix, vendor, date, final_index)
        csv_filename = filename.replace(".pdf", ".csv")

        confidence = compute_statement_confidence(
            statement_pages, vendor, end_keywords, used_fallback
        )

        # Extract transactions
        transactions = extract_transactions(statement_pages, vendor, date)
        csv_content  = transactions_to_csv(transactions, vendor)

        JSON_LOG.log_statement_result(
            pdf_path=path,
            filename=filename,
            vendor=vendor,
            date=date,
            index=final_index,
            confidence=confidence,
            used_fallback=used_fallback,
        )

        results.append({
            "filename":      filename,
            "csv_filename":  csv_filename,
            "csv_content":   csv_content,
            "vendor":        vendor,
            "date":          date,
            "index":         final_index,
            "confidence":    confidence,
            "used_fallback": used_fallback,
            "pages":         statement_pages,
            "transactions":  len(transactions),
        })

        print(f"  → {filename} ({len(statement_pages)} pages, {len(transactions)} transactions, confidence={confidence})")

    return results
