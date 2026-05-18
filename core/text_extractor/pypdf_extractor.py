import pypdf

def extract_page_text(pdf_path: str, page_number: int) -> str:
    """
    Baseline extractor using pypdf.
    Deterministic, simple, good for digital PDFs.
    """
    try:
        reader = pypdf.PdfReader(pdf_path)
        page = reader.pages[page_number]
        return page.extract_text() or ""
    except Exception:
        return ""