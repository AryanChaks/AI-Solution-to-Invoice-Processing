"""Demo data: fictional vendors, POs, one historical invoice with partial payments."""
from datetime import date
from decimal import Decimal as D
from .connection import engine, SessionLocal
from .models import Base, Vendor, VendorAlias, PurchaseOrder, POLineItem, ToleranceSetting
from ..extraction.normalizer import normalize_vendor_name
from ..services import invoice_service, payment_service
from ..validation.financial_validator import q

VENDORS = [
    ("Apex Industrial Supplies Pvt Ltd", "27AAAPA1234A1Z5", "APX", True, ["Apex Industrial"]),
    ("Bluewave Logistics Pvt Ltd", "29BBBCB5678B1Z3", "BWL", True, ["Blue Wave Logistics"]),
    ("Crestline Office Solutions Pvt Ltd", "07CCCDC9012C1Z1", "CRS", True, []),
    ("Dunmore Traders Pvt Ltd", "33DDDED3456D1Z9", "DUN", False, []),   # deliberately UNAPPROVED
]
# (po_number, vendor_idx, date, status, [(code, desc, qty, price, tax)])
POS = [
    ("PO-1001", 0, date(2025, 12, 20), "OPEN", [("WID-01", "Steel Widget", 100, 1000, 18)]),
    ("PO-1002", 0, date(2025, 12, 22), "OPEN", [("MNT-01", "Maintenance Service Hour", 100, 1000, 0)]),
    ("PO-2001", 1, date(2026, 1, 2), "OPEN", [("FRT-01", "Freight Charges Pallet", 100, 1000, 18)]),
    ("PO-2002", 1, date(2026, 1, 5), "OPEN", [("FRT-02", "Warehouse Handling Hour", 50, 2000, 0)]),
    ("PO-3001", 2, date(2026, 1, 10), "OPEN", [("OFF-01", "Office Chair", 20, 5500, 18), ("OFF-02", "Desk Lamp", 50, 800, 18)]),
    ("PO-3002", 2, date(2026, 1, 12), "OPEN", [("PAP-01", "Printer Paper A4 Box", 200, 450, 12)]),
    ("PO-4001", 1, date(2026, 1, 15), "CANCELLED", [("FRT-01", "Freight Charges Pallet", 10, 1000, 18)]),
]

def reset():
    Base.metadata.drop_all(engine)

def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Vendor).count():
            return "Database already has data; use --reset --yes to recreate."
        vs = []
        for name, gstin, code, appr, aliases in VENDORS:
            v = Vendor(Vendor_Name=name, Normalized_Vendor_Name=normalize_vendor_name(name), Tax_ID=gstin, Vendor_Code=code,
                       Is_Approved=appr, Is_Active=True, Email=f"ap@{code.lower()}.example", Primary_Address="Fictional address")
            v.aliases = [VendorAlias(Alias=a, Normalized_Alias=normalize_vendor_name(a)) for a in aliases]
            db.add(v); vs.append(v)
        db.flush()
        pos = {}
        for num, vi, d, st, lines in POS:
            po = PurchaseOrder(PO_Number=num, Vendor_ID=vs[vi].Vendor_ID, PO_Date=d, Currency="INR", PO_Status=st, PO_Total_Amount=0)
            total = D(0)
            for code, desc, qty, pr, tx in lines:
                amt = q(D(qty) * D(pr)); total += amt + q(amt * D(tx) / 100)
                po.lines.append(POLineItem(Item_Code=code, Description=desc, Quantity=D(qty), Unit_Price=D(pr), Tax_Rate=D(tx), Line_Total=amt))
            po.PO_Total_Amount = total; db.add(po); pos[num] = po
        db.flush()
        # Historical invoice against PO-2002 (60,000 of 100,000) with two partial UPI payments
        d = {"invoice_number": "BWL-7700", "norm_number": "BWL7700", "invoice_date": date(2026, 1, 20), "due_date": date(2026, 2, 19),
             "currency": "INR", "subtotal": D(60000), "tax": D(0), "discount": D(0), "other": D(0), "total": D(60000),
             "lines": [{"description": "Warehouse Handling Hour", "item_code": "FRT-02", "quantity": D(30), "unit_price": D(2000), "tax_rate": D(0)}]}
        inv = invoice_service.create_invoice(db, d, vs[1].Vendor_ID, pos["PO-2002"].PO_ID, "MANUAL", "APPROVED", "APPROVED")
        payment_service.add_payment(db, inv, D(20000), date(2026, 2, 1), "UPI", "411111111111", "MANUAL")
        payment_service.add_payment(db, inv, D(15000), date(2026, 2, 8), "UPI", "422222222222", "MANUAL")
        for k, v in {"abs_amount": "1.00", "pct_amount": "0.5", "po_overrun_abs": "0.00", "po_overrun_pct": "2.0",
                     "price_variance_pct": "1.0", "min_field_confidence": "0.75"}.items():
            db.add(ToleranceSetting(Key=k, Value=v))
        db.commit()
    return "Seeded 4 vendors (1 unapproved), 7 POs, 1 historical invoice with 2 partial payments."
