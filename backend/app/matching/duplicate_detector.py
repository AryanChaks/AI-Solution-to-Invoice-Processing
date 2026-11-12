"""Duplicate classification with recorded reasons."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional

@dataclass
class ExistingInvoice:
    invoice_id: int
    vendor_id: int
    norm_number: str
    invoice_date: Optional[date]
    total: Decimal
    file_hashes: List[str] = field(default_factory=list)

@dataclass
class DupResult:
    outcome: str   # NEW | EXISTING_UPDATE | CONFIRMED_DUPLICATE | POTENTIAL_DUPLICATE
    invoice_id: Optional[int]
    reasons: List[str]

def classify(vendor_id: Optional[int], norm_number: str, invoice_date, total, file_hash: Optional[str],
             existing: List[ExistingInvoice]) -> DupResult:
    # 1. Same file bytes already processed -> idempotent no-op
    for e in existing:
        if file_hash and file_hash in e.file_hashes:
            return DupResult("CONFIRMED_DUPLICATE", e.invoice_id, ["Identical file hash already processed."])
    # 2. Vendor + normalised number is THE identity key
    if vendor_id is not None and norm_number:
        for e in existing:
            if e.vendor_id == vendor_id and e.norm_number == norm_number:
                same = (e.total == total) and (e.invoice_date == invoice_date)
                if same:
                    return DupResult("CONFIRMED_DUPLICATE", e.invoice_id,
                        ["Same vendor + invoice number; date and total identical (different channel/file)."])
                return DupResult("EXISTING_UPDATE", e.invoice_id,
                    ["Same vendor + invoice number but date/total differ: treated as update; conflicts go to review."])
    # 3. Weaker signal: same vendor, date, amount, different number
    for e in existing:
        if vendor_id is not None and e.vendor_id == vendor_id and e.invoice_date == invoice_date \
           and e.total == total and e.norm_number != norm_number:
            return DupResult("POTENTIAL_DUPLICATE", e.invoice_id,
                ["Same vendor, date and total under a different invoice number."])
    return DupResult("NEW", None, ["No matching vendor+invoice number, hash or vendor/date/amount."])
