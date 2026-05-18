import fitz  # PyMuPDF

def extract_page_text(pdf_path: str, page_number: int) -> str:
    """
    Fast, layout-aware extractor.
    Often the best first choice.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_number)
        text = page.get_text("text")
        doc.close()
        return text or ""
    except Exception:
        return ""
