# core/pdf_loader.py

import fitz
from core.image_extractor import extract_page

def load_pdf(path: str):
    """
    Load a PDF and return a list of valid PageResult objects.
    Any page that fails extraction is skipped.
    """
    pages = []

    try:
        doc = fitz.open(path)
    except Exception as e:
        print(f"ERROR: Could not open PDF {path}: {e}")
        return []

    for page_number in range(len(doc)):
        try:
            result = extract_page(doc, page_number, path)
            if result:
                pages.append(result)
            else:
                print(f"WARNING: Page {page_number} returned None and was skipped.")
        except Exception as e:
            print(f"ERROR extracting page {page_number}: {e}")

    doc.close()
    return pages
