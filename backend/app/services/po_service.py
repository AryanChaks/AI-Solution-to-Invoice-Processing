from decimal import Decimal
from sqlalchemy import select
from ..database.models import PurchaseOrder, Invoice, POLineItem
from ..matching.po_matcher import POInfo, POLine, CONSUMING_STATUSES

def to_info(po: PurchaseOrder) -> POInfo:
    return POInfo(po.PO_ID, po.Vendor_ID, po.Currency, po.PO_Total_Amount, po.PO_Status,
                  [POLine(l.Item_Code, l.Description, l.Quantity, l.Unit_Price) for l in po.lines])

def find_by_number(db, num: str):
    if not num: return None
    key = "".join(ch for ch in num.upper() if ch.isalnum())
    for po in db.query(PurchaseOrder).all():
        if "".join(ch for ch in po.PO_Number.upper() if ch.isalnum()) == key:
            return po
    return None

def prior_invoices(db, po_id: int, exclude_invoice_id=None, lock=False):
    """[(status, total)] of invoices already consuming this PO. lock=True takes an UPDLOCK on SQL Server
    so concurrent runs serialise on the same PO (the caller re-checks inside its transaction)."""
    if lock:
        stmt = select(PurchaseOrder.PO_ID).where(PurchaseOrder.PO_ID == po_id).with_hint(
            PurchaseOrder, "WITH (UPDLOCK, ROWLOCK)", "mssql")
        db.execute(stmt).all()
    q = db.query(Invoice).filter(Invoice.PO_ID == po_id)
    if exclude_invoice_id:
        q = q.filter(Invoice.Invoice_ID != exclude_invoice_id)
    return [(i.Invoice_Status, i.Total_Amount) for i in q.all()]

def po_summary(db, po: PurchaseOrder) -> dict:
    invs = db.query(Invoice).filter(Invoice.PO_ID == po.PO_ID).all()
    invoiced = sum((i.Total_Amount for i in invs if i.Invoice_Status in CONSUMING_STATUSES), Decimal(0))
    return {"po_total": po.PO_Total_Amount, "invoiced": invoiced, "remaining": po.PO_Total_Amount - invoiced,
            "paid": sum((i.Total_Paid for i in invs), Decimal(0)),
            "outstanding": sum((i.Outstanding_Amount for i in invs if i.Invoice_Status in CONSUMING_STATUSES), Decimal(0)),
            "invoice_count": len(invs)}
