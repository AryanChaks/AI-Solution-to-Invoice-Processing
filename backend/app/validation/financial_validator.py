"""Independent financial reconciliation. Decimal only; no LLM involvement."""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from .tolerance import TolerancePolicy

TWO = Decimal("0.01")
def q(x: Decimal) -> Decimal:
    return x.quantize(TWO, rounding=ROUND_HALF_UP)

@dataclass
class Line:
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0")       # percent
    line_total: Optional[Decimal] = None   # as printed on the invoice
    item_code: Optional[str] = None

@dataclass
class Finding:
    code: str
    severity: str   # INFO | WARNING | ERROR
    message: str

@dataclass
class ReconResult:
    calc_subtotal: Decimal
    calc_tax: Decimal
    expected_total: Decimal
    stated_total: Optional[Decimal]
    difference: Optional[Decimal]
    ok: bool
    steps: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)

def reconcile(lines: List[Line], stated_total: Optional[Decimal], stated_tax: Optional[Decimal] = None,
              discount: Decimal = Decimal(0), other_charges: Decimal = Decimal(0),
              policy: TolerancePolicy = TolerancePolicy()) -> ReconResult:
    steps, findings = [], []
    if not lines:
        findings.append(Finding("NO_LINE_ITEMS", "ERROR", "No line items; cannot verify subtotal."))
        return ReconResult(Decimal(0), Decimal(0), Decimal(0), stated_total, None, False, steps, findings)

    subtotal, tax = Decimal(0), Decimal(0)
    for i, l in enumerate(lines, 1):
        calc = q(l.quantity * l.unit_price)
        steps.append(f"Line {i}: {l.quantity} x {l.unit_price} = {calc}")
        if l.line_total is not None and not policy.within(calc, l.line_total):
            findings.append(Finding("LINE_TOTAL_MISMATCH", "ERROR",
                            f"Line {i} printed total {l.line_total} != qty x price {calc}"))
        subtotal += calc
        tax += q(calc * l.tax_rate / Decimal(100))
    subtotal, tax = q(subtotal), q(tax)
    steps.append(f"Subtotal = {subtotal}; computed tax = {tax}")

    tax_known = any(l.tax_rate > 0 for l in lines)   # if no line carries a rate, invoice-level tax is authoritative
    if stated_tax is not None and tax_known and not policy.within(tax, stated_tax):
        findings.append(Finding("TAX_MISMATCH", "ERROR", f"Stated tax {stated_tax} != computed {tax}"))
    tax_used = stated_tax if stated_tax is not None else tax
    if not tax_known and stated_tax is None:
        findings.append(Finding("TAX_UNVERIFIED", "WARNING", "No tax rate on lines and no stated tax."))
    expected = q(subtotal + tax_used + other_charges - discount)
    steps.append(f"Expected total = {subtotal} + {tax_used} + {other_charges} - {discount} = {expected}")

    diff = None
    if stated_total is None:
        findings.append(Finding("TOTAL_MISSING", "ERROR", "Invoice total not found."))
    else:
        diff = q(stated_total - expected)
        if not policy.within(expected, stated_total):
            findings.append(Finding("TOTAL_MISMATCH", "ERROR", f"Stated total {stated_total} != expected {expected} (diff {diff})"))
    ok = not any(f.severity == "ERROR" for f in findings)
    return ReconResult(subtotal, tax, expected, stated_total, diff, ok, steps, findings)


def reconcile_header(subtotal, tax, discount, other, stated_total, policy: TolerancePolicy = TolerancePolicy(),
                     severity_no_lines: str = "WARNING") -> ReconResult:
    """Header-only check for invoices without line items (e.g. spreadsheet imports)."""
    findings = [Finding("NO_LINE_ITEMS", severity_no_lines, "No line items: line-level and PO price checks skipped.")]
    steps = []
    if stated_total is None:
        findings.append(Finding("TOTAL_MISSING", "ERROR", "Invoice total not found."))
        return ReconResult(subtotal or Decimal(0), tax or Decimal(0), Decimal(0), None, None, False, steps, findings)
    if subtotal is None:
        findings.append(Finding("SUBTOTAL_UNVERIFIED", "WARNING", "No subtotal supplied; total cannot be cross-checked."))
        return ReconResult(Decimal(0), tax or Decimal(0), stated_total, stated_total, Decimal(0),
                           not any(f.severity == "ERROR" for f in findings), steps, findings)
    expected = q(subtotal + (tax or 0) + (other or 0) - (discount or 0))
    steps.append(f"Expected total = {subtotal} + {tax or 0} + {other or 0} - {discount or 0} = {expected}")
    diff = q(stated_total - expected)
    if not policy.within(expected, stated_total):
        findings.append(Finding("TOTAL_MISMATCH", "ERROR", f"Stated total {stated_total} != expected {expected} (diff {diff})"))
    return ReconResult(subtotal, tax or Decimal(0), expected, stated_total, diff,
                       not any(f.severity == "ERROR" for f in findings), steps, findings)
