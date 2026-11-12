"""Deterministic normalisation of identifiers, amounts and dates."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

def normalize_invoice_number(raw: Optional[str]) -> str:
    """'inv - 0042 ' / 'INV/0042' / 'INV0042' -> 'INV0042'. Keeps leading zeros (they can be significant)."""
    if not raw:
        return ""
    return re.sub(r"[^A-Z0-9]", "", raw.upper())

def normalize_vendor_name(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = re.sub(r"[^a-z0-9 ]", " ", raw.lower())
    s = re.sub(r"\b(pvt|private|ltd|limited|llp|inc|co|corp|the)\b", " ", s)
    return " ".join(s.split())

def normalize_utr(raw: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())

def parse_amount(raw) -> Optional[Decimal]:
    """Handles ₹1,00,000.50 / 1,000.00 / (500) negatives. Returns None if unparseable (never guesses)."""
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    s = str(raw).strip()
    neg = (s.startswith("(") and s.endswith(")")) or s.startswith("-")
    s = re.sub(r"[^\d.]", "", s)
    if not s or s.count(".") > 1:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if neg else d

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d/%m/%y"]

def parse_date(raw) -> Optional[date]:
    """Day-first (Indian convention). Returns None rather than guessing."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = (str(raw) if raw is not None else "").strip()
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None
