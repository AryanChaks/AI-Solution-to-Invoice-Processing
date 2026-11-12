"""Single home for business rules + final decision. Deterministic; the LLM never reaches this layer."""
from dataclasses import dataclass, field
from typing import List, Optional
from .financial_validator import Finding

@dataclass
class Facts:
    invoice_number: Optional[str]
    invoice_date: Optional[object]
    total: Optional[object]
    vendor_resolved: bool
    vendor_approved: bool
    po_found: bool
    po_ambiguous: bool = False
    dup_outcome: str = "NEW"
    extraction_failed: bool = False
    low_confidence_fields: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)  # from recon / PO / price checks

@dataclass
class Decision:
    status: str
    passed: List[str]
    failed: List[str]
    warnings: List[str]
    explanation: str
    next_action: str

# code -> hard stop (BLOCKED) instead of review
BLOCKING_CODES = {"CURRENCY_MISMATCH", "PO_NOT_OPEN", "PO_VENDOR_MISMATCH"}

def decide(f: Facts) -> Decision:
    passed, failed, warns, blocked = [], [], [], []
    def rule(name, ok, hard=False):
        (passed if ok else failed).append(name)
        if not ok and hard:
            blocked.append(name)
    rule("Invoice number present", bool(f.invoice_number))
    rule("Invoice date present", f.invoice_date is not None)
    rule("Invoice total present", f.total is not None)
    rule("Vendor resolved", f.vendor_resolved)
    rule("Vendor approved", f.vendor_approved or not f.vendor_resolved, hard=f.vendor_resolved)
    rule("PO found", f.po_found)
    rule("PO match unambiguous", not f.po_ambiguous)
    rule("Not a confirmed duplicate", f.dup_outcome != "CONFIRMED_DUPLICATE", hard=True)
    rule("No potential duplicate", f.dup_outcome != "POTENTIAL_DUPLICATE")
    rule("Extraction succeeded", not f.extraction_failed)
    rule("Field confidence adequate", not f.low_confidence_fields)
    for fi in f.findings:
        if fi.severity == "ERROR":
            failed.append(f"{fi.code}: {fi.message}")
            if fi.code in BLOCKING_CODES:
                blocked.append(fi.code)
        elif fi.severity == "WARNING":
            warns.append(f"{fi.code}: {fi.message}")
    if blocked:
        st, nxt = "BLOCKED", "Resolve hard-stop condition (vendor/PO/duplicate/currency) before reprocessing."
    elif failed:
        st, nxt = "REVIEW_REQUIRED", "Reviewer to inspect failed rules, correct fields or approve with a reason."
    else:
        st, nxt = "AUTO_APPROVED_FOR_AP", "Proceed to AP approval. Payment authorisation is a separate step."
    expl = f"{len(passed)} rules passed, {len(failed)} failed -> {st}." + (f" Failed: {'; '.join(failed)}" if failed else "")
    return Decision(st, passed, failed, warns, expl, nxt)
