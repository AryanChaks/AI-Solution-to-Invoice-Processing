"""Integration tests: real LangGraph run + SQLAlchemy on SQLite. Covers the four mandatory edge cases and more."""
import json
from datetime import date
from decimal import Decimal as D
import pytest
from app.database.connection import SessionLocal
from app.database.models import Invoice, Payment, ProcessingRun, Vendor, PurchaseOrder
from app.services.payment_service import add_payment, PaymentError
from app.utils.runs import create_run
from app.workflow.graph import run_workflow

def vid(db, code): return db.query(Vendor).filter_by(Vendor_Code=code).one().Vendor_ID

def go(vendor_code, number, po, lines, total, tax="0", date_="10/02/2026", source="MANUAL", payment=None, name=None, **extra):
    with SessionLocal() as db:
        v = vid(db, vendor_code) if vendor_code else None
        run = create_run(db, source)
    inv = {"invoice_number": number, "invoice_date": date_, "po_number": po, "total": str(total), "tax": str(tax),
           "currency": extra.get("currency", "INR"), "vendor_name": name, "subtotal": extra.get("subtotal")}
    raw = {"invoice": inv, "lines": [dict(description=d, item_code=c, quantity=str(q), unit_price=str(p), tax_rate=str(t))
                                     for c, d, q, p, t in lines], "gstins": [], "vendor_id": v, "payment": payment}
    run_workflow(run.Run_ID, {"source": source, "skip_extraction": True, "raw": raw})
    with SessionLocal() as db:
        r = db.get(ProcessingRun, run.Run_ID)
        return r.Final_Decision, json.loads(r.Decision_Json), r.Invoice_ID

W = ("WID-01", "Steel Widget", 100, 1000, 18)
M = lambda n: ("MNT-01", "Maintenance Service Hour", n, 1000, 0)

def test_happy_path_auto_approved():
    dec, d, iid = go("APX", "INV-2026-0042", "PO-1001", [W], "118000", "18000")
    assert dec == "AUTO_APPROVED_FOR_AP" and iid
    with SessionLocal() as db: assert db.get(Invoice, iid).Invoice_Status == "AUTO_APPROVED_FOR_AP"

def test_edge2_multiple_invoices_one_po_third_flagged():
    assert go("APX", "A-1", "PO-1002", [M(40)], "40000")[0] == "AUTO_APPROVED_FOR_AP"
    assert go("APX", "A-2", "PO-1002", [M(35)], "35000")[0] == "AUTO_APPROVED_FOR_AP"
    dec, d, _ = go("APX", "A-3", "PO-1002", [M(30)], "30000")
    assert dec == "REVIEW_REQUIRED"
    assert any("PO_OVERRUN" in f for f in d["decision"]["failed"])
    assert d["consumption"]["remaining_before"] == "25000.00"

def test_edge3_duplicate_via_other_channel_no_new_records():
    _, _, first = go("CRS", "CR-5001", "PO-3001", [("OFF-01", "Office Chair", 20, 5500, 18), ("OFF-02", "Desk Lamp", 50, 800, 18)], "177000", "27000", "20/02/2026", "PDF")
    with SessionLocal() as db: before = (db.query(Invoice).count(), db.query(Payment).count())
    dec, d, iid = go("CRS", "CR 5001", "PO-3001", [], "177000", "27000", "20-02-2026", "EXCEL", subtotal="150000")
    assert dec == "BLOCKED" and d["dup"]["outcome"] == "CONFIRMED_DUPLICATE" and iid == first
    with SessionLocal() as db: assert (db.query(Invoice).count(), db.query(Payment).count()) == before

def test_edge4_price_discrepancy_routes_to_review():
    dec, d, _ = go("BWL", "BWL-7788", "PO-2001", [("FRT-01", "Freight Charges Pallet", 100, 1100, 18)], "129800", "19800")
    assert dec == "REVIEW_REQUIRED"
    assert any("PRICE_VARIANCE" in f and "10000.00" in f for f in d["decision"]["failed"])

def test_unknown_vendor_no_invoice_created():
    dec, d, iid = go(None, "X-1", "PO-1001", [W], "118000", "18000", name="Totally Unknown Co")
    assert dec == "REVIEW_REQUIRED" and iid is None

def test_unapproved_vendor_blocked():
    dec, _, _ = go("DUN", "D-1", None, [W], "118000", "18000")
    assert dec == "BLOCKED"

def test_no_matching_po_review():
    dec, d, _ = go("APX", "N-1", None, [("ZZZ", "Unrelated thing", 1, 100, 0)], "100")
    assert dec == "REVIEW_REQUIRED"

def test_closed_or_cancelled_po_blocked():
    dec, _, _ = go("BWL", "C-1", "PO-4001", [("FRT-01", "Freight Charges Pallet", 10, 1000, 18)], "11800", "1800")
    assert dec == "BLOCKED"

def test_currency_mismatch_blocked():
    dec, _, _ = go("APX", "CUR-1", "PO-1001", [W], "118000", "18000", currency="USD")
    assert dec == "BLOCKED"

def test_incorrect_tax_review():
    dec, d, _ = go("APX", "TAX-1", "PO-1001", [W], "120000", "20000")
    assert dec == "REVIEW_REQUIRED" and any("TAX_MISMATCH" in f for f in d["decision"]["failed"])

def test_missing_invoice_number_and_total():
    assert go("APX", "", "PO-1001", [W], "118000")[0] == "REVIEW_REQUIRED"
    dec, _, iid = go("APX", "NT-1", "PO-1001", [W], "")
    assert dec == "REVIEW_REQUIRED" and iid is None

def test_same_invoice_number_different_vendors_allowed():
    a = go("APX", "SAME-1", "PO-1001", [W], "118000", "18000")[2]
    b = go("CRS", "SAME-1", "PO-3002", [("PAP-01", "Printer Paper A4 Box", 200, 450, 12)], "100800", "10800")[2]
    assert a and b and a != b

def test_revised_values_on_approved_invoice_flagged_not_overwritten():
    _, _, iid = go("APX", "REV-1", "PO-1001", [W], "118000", "18000")
    dec, d, iid2 = go("APX", "REV-1", "PO-1001", [("WID-01", "Steel Widget", 100, 900, 18)], "106200", "16200")
    assert iid2 == iid and dec == "REVIEW_REQUIRED"
    with SessionLocal() as db: assert db.get(Invoice, iid).Total_Amount == D("118000.00")

def test_payments_partial_and_repeated_utr():
    with SessionLocal() as db:
        inv = db.query(Invoice).filter_by(Normalized_Invoice_Number="BWL7700").one()
        assert inv.Total_Paid == D("35000.00") and inv.Outstanding_Amount == D("25000.00")
        with pytest.raises(PaymentError): add_payment(db, inv, D(100), date(2026, 3, 1), "UPI", "4111-1111 1111")
        with pytest.raises(PaymentError): add_payment(db, inv, D(30000), date(2026, 3, 1), "UPI", "999999999999")  # overpay

def test_reupload_never_creates_payment():
    pay = {"amount": "5000", "date": "11/02/2026", "ref": "UTR555555555555", "method": "UPI"}
    _, _, iid = go("APX", "PAY-1", "PO-1001", [W], "118000", "18000", payment=pay)
    go("APX", "PAY-1", "PO-1001", [W], "118000", "18000")           # same invoice again, no payment info
    go("APX", "PAY-1", "PO-1001", [W], "118000", "18000", payment=pay)  # same UTR again
    with SessionLocal() as db: assert db.query(Payment).filter_by(Invoice_ID=iid).count() == 1

def test_corrupt_pdf_fails_cleanly(tmp_path):
    bad = tmp_path / "bad.pdf"; bad.write_bytes(b"this is not a pdf")
    with SessionLocal() as db: run = create_run(db, "PDF", "bad.pdf", str(bad))
    run_workflow(run.Run_ID, {"source": "PDF", "file_path": str(bad), "file_name": "bad.pdf"})
    with SessionLocal() as db: assert db.get(ProcessingRun, run.Run_ID).Final_Decision == "FAILED"

def test_empty_excel_and_invalid_mapping():
    from app.services import excel_import as xl
    with pytest.raises(xl.ImportError_): xl.read_table(b"a,b,c\n", "x.csv")
    errs = xl.validate_mapping({"invoice_number": "A", "vendor_name": "A", "invoice_date": "Z"}, ["A", "B"])
    assert any("required" in e for e in errs) and any("does not exist" in e for e in errs) and any("more than one" in e for e in errs)
