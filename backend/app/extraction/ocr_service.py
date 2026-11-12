"""Tesseract OCR wrapper. Returns words in PDF-point coordinates so bboxes are comparable with digital PDFs."""
import logging
from typing import List
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from ..config import settings

log = logging.getLogger(__name__)
if settings.tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path

class OCRUnavailable(RuntimeError):
    pass

def tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False

def preprocess(img: Image.Image) -> Image.Image:
    g = ImageOps.grayscale(img)
    if g.width < 1600:  # upscale small images for better recognition
        f = 1600 / g.width
        g = g.resize((int(g.width * f), int(g.height * f)), Image.LANCZOS)
    g = ImageOps.autocontrast(g)
    return g.filter(ImageFilter.MedianFilter(3))

def ocr_image(img: Image.Image, page_no: int, orig_dpi: float = 200.0) -> dict:
    """Returns {'words': [...], 'text': str, 'avg_conf': 0..1}. Coordinates scaled to PDF points (72/in)."""
    if not tesseract_available():
        raise OCRUnavailable("Tesseract not found. Install it and set TESSERACT_PATH in backend/.env")
    orig_w = img.width
    pre = preprocess(img)
    scale = (orig_w / pre.width) * 72.0 / orig_dpi  # preprocessed px -> points
    d = pytesseract.image_to_data(pre, output_type=pytesseract.Output.DICT, config="--psm 6")
    words, lines, confs = [], {}, []
    for i, t in enumerate(d["text"]):
        t = (t or "").strip()
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not t or conf < 0:
            continue
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        words.append({"page": page_no, "text": t, "x0": x * scale, "y0": y * scale,
                      "x1": (x + w) * scale, "y1": (y + h) * scale, "conf": conf / 100.0})
        confs.append(conf / 100.0)
        lines.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(t)
    text = "\n".join(" ".join(v) for _, v in sorted(lines.items()))
    return {"words": words, "text": text, "avg_conf": sum(confs) / len(confs) if confs else 0.0}
