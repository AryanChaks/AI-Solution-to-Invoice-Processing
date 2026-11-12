"""Parse OCR text of a UPI screenshot into UTR + amount. Pure function; OCR is done elsewhere.
Returns None for anything not found -- the UI pre-fills these and lets the user correct/enter manually."""
import re
from decimal import Decimal
from typing import Optional
from .normalizer import parse_amount, normalize_utr

_UTR = [r"(?:UTR|UPI\s*Ref(?:erence)?(?:\s*(?:No|Number|ID))?|Transaction\s*ID|Ref(?:erence)?\s*(?:No|Number))\.?\s*[:#-]?\s*([A-Z0-9]{10,22})",
        r"\b(\d{12})\b"]  # standard UPI UTR is 12 digits; used only as a fallback
_AMT = [r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)", r"(?:Amount|Paid)\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)"]

def parse_upi_text(text: str) -> dict:
    utr, utr_src = None, None
    for i, pat in enumerate(_UTR):
        m = re.search(pat, text, re.I)
        if m:
            utr, utr_src = normalize_utr(m.group(1)), ("labelled" if i == 0 else "12-digit fallback")
            break
    amount: Optional[Decimal] = None
    for pat in _AMT:
        m = re.search(pat, text, re.I)
        if m:
            amount = parse_amount(m.group(1)); break
    return {"utr": utr, "utr_source": utr_src, "amount": amount}
