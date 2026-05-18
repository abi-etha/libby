import logging
import pypdf
from pathlib import Path

from .pymupdf_extractor import extract_page_text as pymupdf_extract
from .pdfminer_extractor import extract_page_text as pdfminer_extract
from .pypdf_extractor import extract_page_text as pypdf_extract
from .ocr_extractor import extract_page_text as ocr_extract

from core.json_logger import JSONLogger
from core.config import LOG_FOLDER   # shared config

# JSON logger using the same log folder as the watcher
JSON_LOG = JSONLogger(LOG_FOLDER / "events.jsonl")

logger = logging.getLogger(__name__)

EXTRACTOR_CHAIN = [
    ("pymupdf", pymupdf_extract),
    ("pdfminer", pdfminer_extract),
    ("pypdf", pypdf_extract),
    ("ocr", ocr_extract),
]


def extract_text(pdf_path: str) -> list[dict]:
    """
    Extracts text from a PDF page-by-page using a progressive fallback chain.

    Returns:
        [
            {
                "page_number": int,
                "text": str,
                "extractor": str,
                "failed_extractors": [str, ...]
            },
            ...
        ]
    """
    results = []

    # Determine number of pages using pypdf (safe + lightweight)
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)

    for page_number in range(total_pages):
        page_result = {
            "page_number": page_number,
            "text": "",
            "extractor": None,
            "failed_extractors": []
        }

        # Try each extractor in order
        for name, extractor in EXTRACTOR_CHAIN:
            try:
                text = extractor(pdf_path, page_number)
            except Exception as e:
                logger.error(
                    f"[EXTRACTOR] {name} crashed on page {page_number} in {pdf_path}: {e}"
                )
                page_result["failed_extractors"].append(name)

                JSON_LOG.log_extractor_event(
                    pdf_path=pdf_path,
                    page_number=page_number,
                    extractor=name,
                    success=False,
                    failed_extractors=page_result["failed_extractors"]
                )
                continue

            if text and text.strip():
                page_result["text"] = text
                page_result["extractor"] = name

                JSON_LOG.log_extractor_event(
                    pdf_path=pdf_path,
                    page_number=page_number,
                    extractor=name,
                    success=True,
                    failed_extractors=page_result["failed_extractors"]
                )
                break

            else:
                page_result["failed_extractors"].append(name)

                JSON_LOG.log_extractor_event(
                    pdf_path=pdf_path,
                    page_number=page_number,
                    extractor=name,
                    success=False,
                    failed_extractors=page_result["failed_extractors"]
                )

        if page_result["extractor"] is None:
            logger.warning(
                f"[EXTRACTOR] All extractors failed for page {page_number} in {pdf_path}. "
                f"Returning empty text."
            )

            JSON_LOG.log_extractor_failure(
                pdf_path=pdf_path,
                page_number=page_number,
                failed_extractors=page_result["failed_extractors"]
            )

        results.append(page_result)

    return results
