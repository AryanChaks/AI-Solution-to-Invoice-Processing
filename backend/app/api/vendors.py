from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import Vendor, VendorAlias, Invoice
from ..extraction.normalizer import normalize_vendor_name
from ..schemas.models import VendorIn
from ..services.common import audit
from ..utils.runs import row

router = APIRouter(prefix="/api/vendors", tags=["vendors"])

def _out(v): return {**row(v), "aliases": [a.Alias for a in v.aliases]}

def _apply(v, b: VendorIn):
    for f in ("Vendor_Name", "Tax_ID", "Vendor_Code", "Primary_Address", "Email", "Contact_Number", "Is_Approved", "Is_Active"):
        setattr(v, f, getattr(b, f))
    if v.Tax_ID: v.Tax_ID = v.Tax_ID.strip().upper()
    v.Normalized_Vendor_Name = normalize_vendor_name(b.Vendor_Name)
    v.aliases.clear()
    for a in b.aliases:
        if a.strip(): v.aliases.append(VendorAlias(Alias=a.strip(), Normalized_Alias=normalize_vendor_name(a)))

@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    return [_out(v) for v in db.query(Vendor).order_by(Vendor.Vendor_Name)]

@router.post("")
def create(b: VendorIn, db: Session = Depends(get_db)):
    if b.Tax_ID and db.query(Vendor).filter(Vendor.Tax_ID == b.Tax_ID.strip().upper()).first():
        raise HTTPException(409, "A vendor with this GSTIN already exists")
    v = Vendor(); _apply(v, b); db.add(v); db.flush()
    audit(db, "Vendor", v.Vendor_ID, "CREATED", new=b.model_dump()); db.commit()
    return _out(v)

@router.get("/{vendor_id}")
def get(vendor_id: int, db: Session = Depends(get_db)):
    v = db.get(Vendor, vendor_id)
    if not v: raise HTTPException(404, "Vendor not found")
    invs = db.query(Invoice).filter_by(Vendor_ID=vendor_id).order_by(Invoice.Invoice_ID.desc()).all()
    return {**_out(v), "invoices": [row(i) for i in invs]}

@router.put("/{vendor_id}")
def update(vendor_id: int, b: VendorIn, db: Session = Depends(get_db)):
    v = db.get(Vendor, vendor_id)
    if not v: raise HTTPException(404, "Vendor not found")
    old = _out(v); _apply(v, b)
    audit(db, "Vendor", vendor_id, "UPDATED", old=old, new=b.model_dump()); db.commit()
    return _out(v)
