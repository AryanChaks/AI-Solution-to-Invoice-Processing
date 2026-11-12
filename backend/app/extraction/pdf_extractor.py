"""Digital-vs-scanned detection and text/word/table extraction."""
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
from ..config import settings
from .ocr_service import ocr_image

MIN_CHARS_PER_PAGE = 80  # below this a page is treated as scanned

def inspect_pdf(path: str) -> dict:
    with fitz.open(path) as doc:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        if doc.page_count > settings.max_pdf_pages:
            raise ValueError(f"PDF has {doc.page_count} pages; limit is {settings.max_pdf_pages}")
        chars = [len(p.get_text("text").strip()) for p in doc]
        sizes = [(p.rect.width, p.rect.height) for p in doc]
    scanned = [c < MIN_CHARS_PER_PAGE for c in chars]
    doc_type = "SCANNED" if all(scanned) else ("MIXED" if any(scanned) else "DIGITAL")
    return {"pages": len(chars), "chars": chars, "scanned_pages": [i for i, s in enumerate(scanned) if s],
            "doc_type": doc_type, "sizes": sizes}

def extract_pdf(path: str, info: dict) -> dict:
    words, texts, tables, confs = [], [], [], []
    ocr_pages = set(info["scanned_pages"])
    with pdfplumber.open(path) as pdf, fitz.open(path) as doc:
        for i, page in enumerate(pdf.pages):
            if i in ocr_pages:
                pix = doc[i].get_pixmap(dpi=200)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                r = ocr_image(img, i + 1, 200.0)
                words += r["words"]; texts.append(r["text"]); confs.append(r["avg_conf"])
                tables.append([])
            else:
                for w in page.extract_words(keep_blank_chars=False):
                    words.append({"page": i + 1, "text": w["text"], "x0": w["x0"], "y0": w["top"],
                                  "x1": w["x1"], "y1": w["bottom"], "conf": None})
                texts.append(page.extract_text() or "")
                try:
                    tables.append(page.extract_tables() or [])
                except Exception:
                    tables.append([])
    return {"words": words, "page_texts": texts, "tables": tables, "ocr_pages": sorted(ocr_pages),
            "avg_ocr_conf": sum(confs) / len(confs) if confs else None}

def extract_image(path: str) -> dict:
    img = Image.open(path).convert("RGB")
    r = ocr_image(img, 1, 200.0)
    return {"words": r["words"], "page_texts": [r["text"]], "tables": [[]], "ocr_pages": [0], "avg_ocr_conf": r["avg_conf"]}
