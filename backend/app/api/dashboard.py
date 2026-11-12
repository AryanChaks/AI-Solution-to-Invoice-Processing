from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database.connection import get_db
from ..database.models import Invoice, ProcessingRun, Vendor
from .processing import _summary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
LIVE = ("AUTO_APPROVED_FOR_AP", "APPROVED", "REVIEW_REQUIRED", "PAID")

@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    inv = db.query(Invoice).all()
    n = len(inv)
    dups = db.query(ProcessingRun).filter(ProcessingRun.Decision_Json.like('%"CONFIRMED_DUPLICATE"%'),
                                          ProcessingRun.Final_Decision == "BLOCKED").count()
    avg = db.query(func.avg(ProcessingRun.Processing_Duration)).filter(ProcessingRun.Processing_Status == "COMPLETED").scalar()
    runs = db.query(ProcessingRun).count()
    return {
        "total_invoices": n,
        "processed": sum(1 for i in inv if i.Decision_Status),
        "auto_approved": sum(1 for i in inv if i.Decision_Status == "AUTO_APPROVED_FOR_AP"),
        "needs_review": sum(1 for i in inv if i.Invoice_Status == "REVIEW_REQUIRED"),
        "rejected_blocked": sum(1 for i in inv if i.Invoice_Status in ("REJECTED", "BLOCKED")),
        "pending_reviews": db.query(ProcessingRun).filter(ProcessingRun.Review_Status == "PENDING").count(),
        "duplicates_detected": dups,
        "total_value": sum((i.Total_Amount for i in inv), Decimal(0)),
        "total_outstanding": sum((i.Outstanding_Amount for i in inv if i.Invoice_Status in LIVE), Decimal(0)),
        "avg_processing_seconds": float(avg) if avg is not None else None,
        "po_match_rate": (sum(1 for i in inv if i.PO_ID) / n * 100) if n else None,
        "total_runs": runs,
        "recent": [_summary(r, db) for r in db.query(ProcessingRun).order_by(ProcessingRun.Run_ID.desc()).limit(8)],
    }

@router.get("/trends")
def trends(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    volume = defaultdict(lambda: defaultdict(int))
    for r in db.query(ProcessingRun).filter(ProcessingRun.Started_At >= since):
        volume[r.Started_At.date().isoformat()][r.Final_Decision or "RUNNING"] += 1
    dist = defaultdict(int)
    for r in db.query(ProcessingRun.Final_Decision, func.count()).group_by(ProcessingRun.Final_Decision):
        dist[r[0] or "RUNNING"] = r[1]
    monthly = defaultdict(Decimal)
    for i in db.query(Invoice).filter(Invoice.Invoice_Status.in_(LIVE)):
        d = i.Invoice_Date or i.Created_At.date()
        monthly[d.strftime("%Y-%m")] += i.Outstanding_Amount
    return {"volume": [{"date": d, **dict(c), "total": sum(c.values())} for d, c in sorted(volume.items())],
            "distribution": [{"name": k, "value": v} for k, v in dist.items()],
            "monthly_outstanding": [{"month": k, "outstanding": v} for k, v in sorted(monthly.items())]}

@router.get("/vendor-stats")
def vendor_stats(db: Session = Depends(get_db)):
    rows = (db.query(Vendor.Vendor_Name, func.sum(Invoice.Total_Amount), func.count(Invoice.Invoice_ID))
            .join(Invoice, Invoice.Vendor_ID == Vendor.Vendor_ID).group_by(Vendor.Vendor_Name).all())
    return sorted([{"vendor": r[0], "value": r[1], "count": r[2]} for r in rows], key=lambda x: -x["value"])
