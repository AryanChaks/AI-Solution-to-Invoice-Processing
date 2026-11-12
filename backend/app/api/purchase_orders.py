from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import PurchaseOrder, POLineItem, Invoice, Vendor
from ..extraction.normalizer import parse_amount, parse_date
from ..schemas.models import POIn
from ..services.common import audit
from ..services.po_service import po_summary
from ..validation.financial_validator import q
from ..utils.runs import row

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])

def _build(po: PurchaseOrder, b: POIn):
    d = parse_date(b.PO_Date)
    if not d: raise HTTPException(422, "Invalid PO date")
    po.PO_Number, po.Vendor_ID, po.PO_Date, po.Currency, po.PO_Status = b.PO_Number.strip(), b.Vendor_ID, d, b.Currency.upper(), b.PO_Status
    po.lines.clear(); total = Decimal(0)
    for l in b.lines:
        qty, pr, tx = parse_amount(l.Quantity), parse_amount(l.Unit_Price), parse_amount(l.Tax_Rate) or Decimal(0)
        if qty is None or pr is None or qty <= 0 or pr < 0: raise HTTPException(422, f"Invalid line '{l.Description}'")
        amt = q(qty * pr); total += amt + q(amt * tx / 100)
        po.lines.append(POLineItem(Item_Code=l.Item_Code, Description=l.Description, Quantity=qty, Unit_Price=pr, Tax_Rate=tx, Line_Total=amt))
    po.PO_Total_Amount = total   # PO total includes line tax

def _out(db, po):
    return {**row(po), "lines": [row(l) for l in po.lines], "summary": po_summary(db, po),
            "Vendor_Name": db.get(Vendor, po.Vendor_ID).Vendor_Name}

@router.get("")
def list_pos(db: Session = Depends(get_db)):
    return [{**row(p), "Vendor_Name": db.get(Vendor, p.Vendor_ID).Vendor_Name, "summary": po_summary(db, p)}
            for p in db.query(PurchaseOrder).order_by(PurchaseOrder.PO_ID.desc())]

@router.post("")
def create(b: POIn, db: Session = Depends(get_db)):
    if db.query(PurchaseOrder).filter_by(PO_Number=b.PO_Number.strip()).first():
        raise HTTPException(409, "PO number already exists")
    po = PurchaseOrder(); _build(po, b); db.add(po); db.flush()
    audit(db, "PurchaseOrder", po.PO_ID, "CREATED", new={"number": po.PO_Number, "total": po.PO_Total_Amount}); db.commit()
    return _out(db, po)

@router.get("/{po_id}")
def get(po_id: int, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "PO not found")
    return {**_out(db, po), "invoices": [row(i) for i in db.query(Invoice).filter_by(PO_ID=po_id).order_by(Invoice.Invoice_ID)]}

@router.put("/{po_id}")
def update(po_id: int, b: POIn, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "PO not found")
    old = {"total": po.PO_Total_Amount, "status": po.PO_Status}
    _build(po, b); audit(db, "PurchaseOrder", po_id, "UPDATED", old=old, new={"total": po.PO_Total_Amount, "status": po.PO_Status}); db.commit()
    return _out(db, po)
