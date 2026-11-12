"""PO consumption + line price checks. Ranking never overrides hard rules (vendor/currency/status)."""
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from ..validation.financial_validator import Finding, Line, q
from ..validation.tolerance import TolerancePolicy

# Invoice statuses that consume PO value. REJECTED/FAILED/DRAFT must NOT count.
CONSUMING_STATUSES = {"AUTO_APPROVED_FOR_AP", "APPROVED", "REVIEW_REQUIRED", "PAID"}

@dataclass
class POLine:
    item_code: Optional[str]
    description: str
    quantity: Decimal
    unit_price: Decimal

@dataclass
class POInfo:
    po_id: int
    vendor_id: int
    currency: str
    total: Decimal
    status: str  # OPEN | CLOSED | CANCELLED
    lines: List[POLine]

def po_consumption(po_total: Decimal, prior_invoices: List[tuple], this_amount: Decimal,
                   policy: TolerancePolicy = TolerancePolicy()):
    """prior_invoices: [(status, amount)] excluding the invoice under evaluation (keeps reprocessing idempotent)."""
    invoiced = sum((a for s, a in prior_invoices if s in CONSUMING_STATUSES), Decimal(0))
    remaining = po_total - invoiced
    over = this_amount - remaining
    allowed = max(policy.po_overrun_abs, remaining * policy.po_overrun_pct / Decimal(100) if remaining > 0 else Decimal(0))
    findings = []
    if over > allowed:
        findings.append(Finding("PO_OVERRUN", "ERROR",
            f"Invoice {this_amount} exceeds remaining PO value {remaining} by {q(over)} (allowed {q(allowed)})."))
    return {"po_total": po_total, "invoiced_before": invoiced, "remaining_before": remaining,
            "remaining_after": remaining - this_amount, "findings": findings}

def hard_checks(po: POInfo, vendor_id: int, currency: str) -> List[Finding]:
    f = []
    if po.vendor_id != vendor_id:
        f.append(Finding("PO_VENDOR_MISMATCH", "ERROR", "PO belongs to a different vendor."))
    if po.currency != currency:
        f.append(Finding("CURRENCY_MISMATCH", "ERROR", f"Invoice {currency} vs PO {po.currency}."))
    if po.status in ("CLOSED", "CANCELLED"):
        f.append(Finding("PO_NOT_OPEN", "ERROR", f"PO status is {po.status}."))
    return f

def price_check(po: POInfo, lines: List[Line], policy: TolerancePolicy = TolerancePolicy()) -> List[Finding]:
    """Match by item code, else exact normalised description. Flags unit price and quantity variance."""
    out = []
    by_code = {l.item_code: l for l in po.lines if l.item_code}
    by_desc = {l.description.strip().lower(): l for l in po.lines}
    for i, il in enumerate(lines, 1):
        pl = by_code.get(il.item_code) or by_desc.get(il.description.strip().lower())
        if pl is None:
            out.append(Finding("LINE_NOT_ON_PO", "WARNING", f"Line {i} '{il.description}' not found on PO."))
            continue
        if il.unit_price != pl.unit_price:
            pct = abs(il.unit_price - pl.unit_price) / pl.unit_price * 100
            impact = q((il.unit_price - pl.unit_price) * il.quantity)
            sev = "ERROR" if pct > policy.price_variance_pct else "INFO"
            out.append(Finding("PRICE_VARIANCE", sev,
                f"Line {i}: invoice price {il.unit_price} vs PO {pl.unit_price} ({q(pct)}%), impact {impact}."))
        if il.quantity > pl.quantity:
            out.append(Finding("QTY_EXCEEDS_PO", "ERROR", f"Line {i}: qty {il.quantity} > PO qty {pl.quantity}."))
    return out


def rank_candidates(pos: List[POInfo], vendor_id: int, currency: str, lines: List[Line], total: Optional[Decimal]):
    """Transparent scoring used ONLY to rank candidates. Vendor mismatch / closed POs are excluded outright."""
    out = []
    for po in pos:
        if po.vendor_id != vendor_id or po.status != "OPEN":
            continue
        parts, score = [], 0
        if po.currency == currency:
            score += 10; parts.append("currency match +10")
        by_code = {l.item_code for l in po.lines if l.item_code}
        by_desc = {l.description.strip().lower() for l in po.lines}
        if lines:
            hit = sum(1 for l in lines if (l.item_code and l.item_code in by_code) or l.description.strip().lower() in by_desc)
            pts = int(50 * hit / len(lines)); score += pts
            parts.append(f"{hit}/{len(lines)} lines match by code/description +{pts}")
            price_ok = sum(1 for l in lines for p in po.lines
                           if (l.item_code and l.item_code == p.item_code) and l.unit_price == p.unit_price)
            pts = int(25 * price_ok / len(lines)); score += pts
            parts.append(f"{price_ok} exact unit-price matches +{pts}")
        if total is not None and total <= po.total:
            score += 15; parts.append("amount within PO total +15")
        out.append({"po_id": po.po_id, "score": score, "parts": parts})
    return sorted(out, key=lambda x: -x["score"])
