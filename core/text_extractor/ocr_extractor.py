import fitz
import pytesseract
from PIL import Image
import io

def extract_page_text(pdf_path: str, page_number: int) -> str:
    """
    OCR fallback for scanned PDFs.
    Converts page → image → OCR text.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        doc.close()

        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception:
        return ""
