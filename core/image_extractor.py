# core/image_extractor.py
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from dataclasses import dataclass
import io

@dataclass
class PageResult:
    page_number: int
    page_type: str          # "digital", "scanned", "mixed"
    text: str               # extracted or OCR'd text
    images: list            # list of dicts: {index, bytes, ext, width, height}
    raw_page_image: bytes   # full-page raster (PNG), always populated
    source_path: str        # NEW: path to original PDF

def classify_page(page: fitz.Page) -> str:
    has_text = bool(page.get_text("text").strip())
    has_images = len(page.get_images(full=True)) > 0
    
    if has_text and has_images:
        return "mixed"
    elif has_text:
        return "digital"
    else:
        return "scanned"

def extract_embedded_images(doc: fitz.Document, page: fitz.Page) -> list:
    images = []
    for i, img_info in enumerate(page.get_images(full=True)):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            images.append({
                "index": i,
                "bytes": base_image["image"],
                "ext": base_image["ext"],
                "width": base_image["width"],
                "height": base_image["height"],
            })
        except Exception:
            continue
    return images

def rasterize_page(page: fitz.Page, dpi: int = 300) -> bytes:
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")

def ocr_image_bytes(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(img).strip()

def extract_page(doc: fitz.Document, page_number: int, source_path: str) -> PageResult:
    """
    Extract a single page into a PageResult.
    Always returns a PageResult or raises an exception.
    """
    page = doc.load_page(page_number)
    page_type = classify_page(page)
    raw_page_image = rasterize_page(page, dpi=150)

    if page_type in ("digital", "mixed"):
        text = page.get_text("text").strip()
        images = extract_embedded_images(doc, page)
    else:
        full_res = rasterize_page(page, dpi=300)
        text = ocr_image_bytes(full_res)
        images = [{
            "index": 0,
            "bytes": full_res,
            "ext": "png",
            "width": page.rect.width,
            "height": page.rect.height
        }]

    return PageResult(
        page_number=page_number,
        page_type=page_type,
        text=text,
        images=images,
        raw_page_image=raw_page_image,
        source_path=source_path,
    )
