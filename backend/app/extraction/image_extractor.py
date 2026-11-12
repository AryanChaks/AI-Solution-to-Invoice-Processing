"""UPI payment screenshot -> {utr, amount, confidence}. Always a suggestion; the UI lets the user edit."""
from PIL import Image
from .ocr_service import ocr_image
from .upi_parser import parse_upi_text

def read_upi_image(path: str) -> dict:
    img = Image.open(path).convert("RGB")
    r = ocr_image(img, 1, 200.0)
    parsed = parse_upi_text(r["text"])
    return {"utr": parsed["utr"], "utr_source": parsed["utr_source"],
            "amount": str(parsed["amount"]) if parsed["amount"] is not None else None,
            "ocr_confidence": round(r["avg_conf"], 3), "raw_text": r["text"][:2000]}
