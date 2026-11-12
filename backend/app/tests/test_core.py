from datetime import date
from decimal import Decimal as D
from ..extraction.normalizer import *
from ..validation.financial_validator import Line, reconcile
from ..validation.rule_engine import Facts, decide
from ..matching.po_matcher import POInfo, POLine, po_consumption, price_check, hard_checks
from ..matching.duplicate_detector import ExistingInvoice, classify

def test_invoice_number_normalisation():
    assert normalize_invoice_number(" inv / 0042 ") == normalize_invoice_number("INV-0042") == "INV0042"

def test_amount_and_date_parsing():
    assert parse_amount("₹1,00,000.50") == D("100000.50")
    assert parse_amount("abc") is None
    assert parse_date("31/01/2026") == date(2026, 1, 31)
    assert parse_date("garbage") is None

def test_utr_normalisation():
    assert normalize_utr("utr: 4123 4567 89") == "UTR41234567" + "89"

def test_reconcile_ok_and_tax_error():
    lines = [Line("Widget", D(10), D("100"), D(18))]
    assert reconcile(lines, D("1180")).ok
    r = reconcile(lines, D("1180"), stated_tax=D("150"))
    assert any(f.code == "TAX_MISMATCH" for f in r.findings) and not r.ok

def test_missing_total_and_no_lines():
    assert not reconcile([Line("x", D(1), D(1))], None).ok
    assert not reconcile([], D(5)).ok

def test_edge2_po_overrun():
    prior = [("AUTO_APPROVED_FOR_AP", D(40000)), ("APPROVED", D(35000))]
    r = po_consumption(D(100000), prior, D(30000))
    assert r["remaining_before"] == D(25000) and r["findings"][0].code == "PO_OVERRUN"
    assert not po_consumption(D(100000), prior, D(25000))["findings"]

def test_rejected_invoices_do_not_consume_po():
    r = po_consumption(D(100000), [("REJECTED", D(90000))], D(50000))
    assert r["remaining_before"] == D(100000) and not r["findings"]

def test_edge4_price_discrepancy():
    po = POInfo(1, 1, "INR", D(100000), "OPEN", [POLine("W-1", "Widget", D(100), D(1000))])
    f = price_check(po, [Line("Widget", D(100), D(1100), item_code="W-1")])
    assert f[0].code == "PRICE_VARIANCE" and f[0].severity == "ERROR" and "10000.00" in f[0].message

def test_po_hard_checks():
    po = POInfo(1, 2, "USD", D(1), "CANCELLED", [])
    codes = {x.code for x in hard_checks(po, 1, "INR")}
    assert codes == {"PO_VENDOR_MISMATCH", "CURRENCY_MISMATCH", "PO_NOT_OPEN"}

def test_edge3_duplicate_across_channels_and_same_number_other_vendor():
    ex = [ExistingInvoice(7, 1, "INV0042", date(2026, 1, 5), D(1180), ["h1"])]
    assert classify(1, "INV0042", date(2026, 1, 5), D(1180), None, ex).outcome == "CONFIRMED_DUPLICATE"
    assert classify(1, "INV0042", date(2026, 1, 5), D(1500), None, ex).outcome == "EXISTING_UPDATE"
    assert classify(2, "INV0042", date(2026, 1, 5), D(1180), None, ex).outcome == "NEW"
    assert classify(1, "X", date(2026, 1, 5), D(1180), None, ex).outcome == "POTENTIAL_DUPLICATE"
    assert classify(9, "Z", None, D(1), "h1", ex).outcome == "CONFIRMED_DUPLICATE"

def _ok(**kw):
    base = dict(invoice_number="A1", invoice_date=date(2026, 1, 1), total=D(1), vendor_resolved=True,
                vendor_approved=True, po_found=True)
    base.update(kw); return Facts(**base)

def test_decisions():
    assert decide(_ok()).status == "AUTO_APPROVED_FOR_AP"
    assert decide(_ok(invoice_number=None)).status == "REVIEW_REQUIRED"
    assert decide(_ok(po_found=False)).status == "REVIEW_REQUIRED"
    assert decide(_ok(vendor_approved=False)).status == "BLOCKED"
    assert decide(_ok(dup_outcome="CONFIRMED_DUPLICATE")).status == "BLOCKED"
    assert decide(_ok(low_confidence_fields=["total"])).status == "REVIEW_REQUIRED"

def test_upi_parse():
    from ..extraction.upi_parser import parse_upi_text
    r = parse_upi_text("Payment Successful\n₹12,500.00\nUPI Ref No: 412345678901\nTo: ACME")
    assert r["utr"] == "412345678901" and r["amount"] == D("12500.00")
    r = parse_upi_text("blurry nothing here")
    assert r["utr"] is None and r["amount"] is None
