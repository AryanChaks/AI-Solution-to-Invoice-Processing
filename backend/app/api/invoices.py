import json, logging, os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import (Invoice, Vendor, Payment, ProcessingRun, PurchaseOrder, ColumnMappingTemplate, AuditLog, ExtractionEvidence)
from ..extraction.normalizer import parse_amount, parse_date
from ..extraction.ocr_service import OCRUnavailable
from ..schemas.models import ManualInvoice, PaymentCreate, InvoiceUpdate
from ..services import excel_import as xl
from ..services.common import audit
from ..services.payment_service import add_payment, PaymentError
from ..utils.files import save_upload, PDF_EXT, IMG_EXT, UPLOAD_ROOT
from ..utils.runs import create_run, start_background, jl, row
from ..workflow.graph import run_workflow
import uuid

router = APIRouter(prefix="/api/invoices", tags=["invoices"])
log = logging.getLogger(__name__)

def _manual_raw(b: ManualInvoice):
    inv = b.model_dump(exclude={"lines", "payment", "vendor_id"})
    return {"invoice": inv, "lines": [l.model_dump() for l in b.lines], "gstins": [], "vendor_id": b.vendor_id,
            "payment": b.payment.model_dump() if b.payment else None}

@router.post("/manual")
def manual(b: ManualInvoice, db: Session = Depends(get_db)):
    if not b.vendor_id and not b.vendor_name:
        raise HTTPException(422, "Select a vendor")
    run = create_run(db, "MANUAL")
    run_workflow(run.Run_ID, {"source": "MANUAL", "skip_extraction": True, "raw": _manual_raw(b)})
    db.refresh(run)
    return {"run_id": run.Run_ID, "decision": run.Final_Decision, "invoice_id": run.Invoice_ID, "detail": jl(run.Decision_Json)}

@router.post("/upload/pdf")
async def upload_pdf(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Accepts PDFs (and scanned images). Each file becomes its own processing run, executed in the background."""
    out = []
    for f in files:
        path, name, h = await save_upload(f, PDF_EXT | IMG_EXT)
        src = "PDF" if path.lower().endswith(".pdf") else "IMAGE"
        run = create_run(db, src, name, path, h)
        start_background(run.Run_ID, {"source": src, "file_path": path, "file_name": name, "file_hash": h})
        out.append({"run_id": run.Run_ID, "file": name})
    return out

@router.post("/payment-image")
async def parse_payment_image(file: UploadFile = File(...)):
    from ..extraction.image_extractor import read_upi_image
    path, name, _ = await save_upload(file, IMG_EXT)
    try:
        return read_upi_image(path)
    except OCRUnavailable as e:
        raise HTTPException(503, str(e))
    finally:
        try: os.remove(path)
        except OSError: pass

# ---------- Excel / CSV ----------
@router.get("/mapping-fields")
def mapping_fields():
    return [{"key": k, "label": l, "required": r} for k, l, r in xl.INTERNAL]

@router.post("/upload/excel/preview")
async def excel_preview(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        df = xl.read_table(content, file.filename or "")
    except xl.ImportError_ as e:
        raise HTTPException(400, str(e))
    cols = list(df.columns)
    return {"columns": cols, "rows": len(df), "preview": df.head(15).to_dict("records"),
            "suggested": xl.suggest_mapping(cols),
            "templates": [{"id": t.Template_ID, "name": t.Name, "mapping": json.loads(t.Mapping_Json)} for t in db.query(ColumnMappingTemplate)]}

@router.post("/upload/excel/commit")
async def excel_commit(file: UploadFile = File(...), mapping: str = Form(...), dry_run: bool = Form(True),
                       template_name: Optional[str] = Form(None), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        df = xl.read_table(content, file.filename or "")
        m = {k: v for k, v in json.loads(mapping).items() if v}
    except (xl.ImportError_, ValueError) as e:
        raise HTTPException(400, str(e))
    errs = xl.validate_mapping(m, list(df.columns))
    if errs:
        raise HTTPException(422, {"mapping_errors": errs})
    if template_name and not dry_run:
        t = db.query(ColumnMappingTemplate).filter_by(Name=template_name).first()
        if t: t.Mapping_Json = json.dumps(m)
        else: db.add(ColumnMappingTemplate(Name=template_name, Mapping_Json=json.dumps(m)))
        db.commit()
    results, ok, bad = [], 0, 0
    for i, (_, r) in enumerate(df.iterrows(), start=2):  # row 1 = header
        inv, pay, errs = xl.row_to_raw(r, m)
        res = {"row": i, "invoice_number": inv.get("invoice_number"), "vendor": inv.get("vendor_name"), "errors": errs}
        if errs:
            bad += 1; res["status"] = "INVALID"
        elif dry_run:
            ok += 1; res["status"] = "VALID"; res.update(xl.preview_duplicate(db, inv))
        else:
            run = create_run(db, "EXCEL", file.filename)
            run_workflow(run.Run_ID, {"source": "EXCEL", "skip_extraction": True, "file_name": file.filename,
                                      "raw": {"invoice": inv, "lines": [], "gstins": [], "payment": pay}})
            db.refresh(run); ok += 1
            res.update(status="IMPORTED", run_id=run.Run_ID, decision=run.Final_Decision, invoice_id=run.Invoice_ID)
        results.append(res)
    return {"dry_run": dry_run, "total_rows": len(df), "ok_rows": ok, "error_rows": bad, "results": results}

@router.get("/mapping-templates")
def templates(db: Session = Depends(get_db)):
    return [{"id": t.Template_ID, "name": t.Name, "mapping": json.loads(t.Mapping_Json)} for t in db.query(ColumnMappingTemplate)]

# ---------- CRUD ----------
@router.get("")
def list_invoices(q: Optional[str] = None, vendor_id: Optional[int] = None, status: Optional[str] = None,
                  limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    qs = db.query(Invoice, Vendor).join(Vendor, Vendor.Vendor_ID == Invoice.Vendor_ID)
    if vendor_id: qs = qs.filter(Invoice.Vendor_ID == vendor_id)
    if status: qs = qs.filter(Invoice.Invoice_Status == status)
    if q: qs = qs.filter(or_(Invoice.Invoice_Number.ilike(f"%{q}%"), Vendor.Vendor_Name.ilike(f"%{q}%")))
    return [{**row(i), "Vendor_Name": v.Vendor_Name} for i, v in qs.order_by(Invoice.Invoice_ID.desc()).limit(limit)]

@router.get("/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    i = db.get(Invoice, invoice_id)
    if not i: raise HTTPException(404, "Invoice not found")
    runs = db.query(ProcessingRun).filter_by(Invoice_ID=invoice_id).order_by(ProcessingRun.Run_ID.desc()).all()
    po = db.get(PurchaseOrder, i.PO_ID) if i.PO_ID else None
    latest = runs[0] if runs else None
    ev = []
    if latest:
        ev = [row(e) for e in db.query(ExtractionEvidence).filter_by(Run_ID=latest.Run_ID)]
    return {"invoice": row(i), "vendor": row(db.get(Vendor, i.Vendor_ID)), "po": row(po) if po else None,
            "lines": [row(l) for l in i.lines], "payments": [row(p) for p in i.payments],
            "runs": [{**row(r, ("Decision_Json", "Parsed_Json"))} for r in runs],
            "decision": jl(latest.Decision_Json) if latest else None, "evidence": ev,
            "latest_run_id": latest.Run_ID if latest else None,
            "has_file": bool(latest and latest.Stored_File_Path),
            "audit": [row(a) for a in db.query(AuditLog).filter(AuditLog.Entity_Type.in_(["Invoice", "Payment"]), AuditLog.Entity_ID == invoice_id).order_by(AuditLog.Audit_ID.desc())]}

@router.put("/{invoice_id}")
def update_invoice(invoice_id: int, b: InvoiceUpdate, db: Session = Depends(get_db)):
    i = db.get(Invoice, invoice_id)
    if not i: raise HTTPException(404, "Invoice not found")
    d = parse_date(b.Due_Date) if b.Due_Date else None
    if b.Due_Date and not d: raise HTTPException(422, "Invalid due date")
    audit(db, "Invoice", i.Invoice_ID, "METADATA_EDIT", old={"Due_Date": i.Due_Date}, new={"Due_Date": d}, reason=b.reason)
    i.Due_Date = d; db.commit()
    return row(i)

@router.get("/{invoice_id}/payments")
def payments(invoice_id: int, db: Session = Depends(get_db)):
    return [row(p) for p in db.query(Payment).filter_by(Invoice_ID=invoice_id).order_by(Payment.Payment_Date)]

@router.post("/{invoice_id}/payments")
def add_pay(invoice_id: int, b: PaymentCreate, db: Session = Depends(get_db)):
    i = db.get(Invoice, invoice_id)
    if not i: raise HTTPException(404, "Invoice not found")
    try:
        p = add_payment(db, i, parse_amount(b.amount), parse_date(b.date), b.method or "UPI" if b.ref else b.method, b.ref,
                        image_amount=parse_amount(b.image_amount) if b.image_amount else None)
        db.commit()
    except PaymentError as e:
        db.rollback(); raise HTTPException(409, str(e))
    return row(p)

@router.get("/{invoice_id}/decision")
def decision(invoice_id: int, db: Session = Depends(get_db)):
    r = db.query(ProcessingRun).filter_by(Invoice_ID=invoice_id).order_by(ProcessingRun.Run_ID.desc()).first()
    if not r: raise HTTPException(404, "No processing run")
    return jl(r.Decision_Json)
