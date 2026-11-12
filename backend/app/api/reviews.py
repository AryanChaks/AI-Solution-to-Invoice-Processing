from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import ProcessingRun, Invoice, Vendor
from ..schemas.models import ReasonIn, CorrectIn
from ..services.common import audit
from ..utils.runs import jl
from .processing import do_reprocess, _summary

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

def _severity(dec):
    st = (dec or {}).get("decision", {}).get("status")
    return "HIGH" if st == "BLOCKED" else "MEDIUM"

@router.get("")
def queue(db: Session = Depends(get_db)):
    out = []
    for r in db.query(ProcessingRun).filter(ProcessingRun.Review_Status == "PENDING").order_by(ProcessingRun.Run_ID.desc()):
        d = jl(r.Decision_Json) or {}
        failed = (d.get("decision") or {}).get("failed") or []
        out.append({**_summary(r, db), "issue": failed[0] if failed else "Review required",
                    "reasons": failed, "severity": _severity(d), "dup": (d.get("dup") or {}).get("outcome")})
    return out

def _run(db, run_id):
    r = db.get(ProcessingRun, run_id)
    if not r or r.Review_Status != "PENDING":
        raise HTTPException(404, "No pending review for this run")
    return r

@router.post("/{run_id}/approve")
def approve(run_id: int, b: ReasonIn, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    if r.Final_Decision == "BLOCKED":
        raise HTTPException(409, "Blocked items (unapproved vendor, duplicate, currency/PO hard-stop) cannot be approved. Fix the cause and reprocess.")
    inv = db.get(Invoice, r.Invoice_ID) if r.Invoice_ID else None
    if not inv:
        raise HTTPException(409, "Invoice identity is unresolved. Correct vendor/number/total and reprocess first.")
    if inv.Invoice_Status != "REVIEW_REQUIRED":
        raise HTTPException(409, f"Invoice is currently {inv.Invoice_Status}; manual approval not applicable.")
    if inv.Total_Amount <= 0:
        raise HTTPException(409, "Cannot approve a non-positive invoice total.")
    audit(db, "Invoice", inv.Invoice_ID, "MANUAL_APPROVE", old={"status": inv.Invoice_Status}, new={"status": "APPROVED"}, reason=b.reason)
    inv.Invoice_Status = inv.Decision_Status = "APPROVED"
    r.Review_Status = "APPROVED"
    db.commit()
    return {"ok": True}

@router.post("/{run_id}/reject")
def reject(run_id: int, b: ReasonIn, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    inv = db.get(Invoice, r.Invoice_ID) if r.Invoice_ID else None
    dup = ((jl(r.Decision_Json) or {}).get("dup") or {}).get("outcome")
    # A rejected duplicate/conflict run must never reject the ORIGINAL approved invoice.
    if inv and inv.Invoice_Status in ("REVIEW_REQUIRED", "BLOCKED") and dup != "CONFIRMED_DUPLICATE":
        audit(db, "Invoice", inv.Invoice_ID, "MANUAL_REJECT", old={"status": inv.Invoice_Status}, new={"status": "REJECTED"}, reason=b.reason)
        inv.Invoice_Status = inv.Decision_Status = "REJECTED"
    else:
        audit(db, "Run", run_id, "DISMISS", reason=b.reason)
    r.Review_Status = "REJECTED"
    db.commit()
    return {"ok": True}

@router.post("/{run_id}/clarify")
def clarify(run_id: int, b: ReasonIn, db: Session = Depends(get_db)):
    r = _run(db, run_id)
    audit(db, "Invoice" if r.Invoice_ID else "Run", r.Invoice_ID or run_id, "CLARIFICATION_REQUESTED", reason=b.reason)
    r.Review_Status = "CLARIFICATION"
    db.commit()
    return {"ok": True}

@router.post("/{run_id}/correct")
def correct(run_id: int, b: CorrectIn, db: Session = Depends(get_db)):
    if not b.corrections:
        raise HTTPException(422, "No corrections supplied")
    r = db.get(ProcessingRun, run_id)
    if not r or r.Review_Status not in ("PENDING", "CLARIFICATION"):
        raise HTTPException(404, "No open review for this run")
    return do_reprocess(db, run_id, b.corrections, b.reason)
