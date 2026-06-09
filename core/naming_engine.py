# core/naming_engine.py
#
# Builds filenames in the format:
#   PREFIX_VENDOR_DOCTYPE_YYYY-MM_001.pdf
# e.g.:
#   ABIGAIL_ATT_UTIL_2025-01_001.pdf
#   ABIGAIL_BOA_BANK_2025-03_001.pdf
#   ABIGAIL_MISC_RCPT_2025-06_001.pdf

from core.page_classifier import doc_type_label


def build_filename(
    prefix: str,
    vendor: str,
    doc_type: str,
    year_month: str,
    index: int,
    confidence: float = None,
) -> str:
    """
    Build a standardized filename for a processed statement.

    Args:
        prefix:     Client/folder prefix (e.g. "ABIGAIL")
        vendor:     Detected vendor (e.g. "ATT", "BOA", "MISC")
        doc_type:   Detected document type (e.g. "utility_bill", "bank_statement")
        year_month: "YYYY-MM" or "unknown"
        index:      Statement number within this batch (1-based)
        confidence: Optional confidence score; appended if low

    Returns:
        Filename string e.g. "ABIGAIL_ATT_UTIL_2025-01_001.pdf"
    """
    prefix_clean  = prefix.strip().upper().replace(" ", "_")
    vendor_clean  = vendor.strip().upper().replace(" ", "")
    type_label    = doc_type_label(doc_type)
    date_clean    = year_month if year_month and year_month != "unknown" else "0000-00"

    conf_suffix = ""
    if confidence is not None and confidence < 0.5:
        conf_suffix = f"_lowconf{int(confidence * 100)}"

    return f"{prefix_clean}_{vendor_clean}_{type_label}_{date_clean}_{index:03d}{conf_suffix}.pdf"


def build_csv_filename(pdf_filename: str) -> str:
    """Derive CSV filename from PDF filename."""
    return pdf_filename.replace(".pdf", ".csv")
