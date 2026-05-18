from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

def extract_page_text(pdf_path: str, page_number: int) -> str:
    """
    Stable reading-order extractor.
    Good fallback when PyMuPDF output is messy.
    """
    try:
        text_chunks = []
        for i, page_layout in enumerate(extract_pages(pdf_path)):
            if i == page_number:
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        text_chunks.append(element.get_text())
                break
        return "".join(text_chunks).strip()
    except Exception:
        return ""
