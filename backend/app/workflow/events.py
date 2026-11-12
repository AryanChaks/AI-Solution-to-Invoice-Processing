import functools, logging, time
from datetime import datetime
from decimal import Decimal
from ..database.connection import SessionLocal
from ..database.models import ProcessingEvent

log = logging.getLogger(__name__)

STAGES = [
    ("n_receive", "Receive invoice"), ("n_validate_file", "File validation"), ("n_inspect", "PDF inspection"),
    ("n_extract_text", "OCR / text extraction"), ("n_structured", "Structured data extraction"),
    ("n_normalize", "Field normalization"), ("n_required", "Required-field validation"),
    ("n_vendor", "Vendor verification"), ("n_identify", "Invoice identification & duplicates"),
    ("n_po_match", "PO matching"), ("n_reconcile", "Financial reconciliation"), ("n_po_consumption", "PO consumption"),
    ("n_rules", "Business rules & decision"), ("n_persist", "Database persistence"), ("n_route", "Review routing"),
]

def _short(o, n=600):
    s = str(o)
    return s if len(s) <= n else s[:n] + "…"

def stage(name):
    """Wraps a node: persists RUNNING -> final event (visible to SSE), converts exceptions into state['error']."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(state):
            t0, started = time.perf_counter(), datetime.utcnow()
            with SessionLocal() as db:
                ev = ProcessingEvent(Run_ID=state["run_id"], Stage_Name=name, Stage_Status="RUNNING", Started_At=started)
                db.add(ev); db.commit(); eid = ev.Event_ID
            out, status, summary, err = {}, "COMPLETED", "", None
            try:
                out = fn(state) or {}
                status = out.pop("_status", "COMPLETED"); summary = out.pop("_summary", "")
            except Exception as e:  # technical failure
                log.exception("Stage %s failed", name)
                status, err, out = "FAILED", f"{type(e).__name__}: {e}", {"error": f"{name}: {e}"}
            dur = Decimal(str(round(time.perf_counter() - t0, 3)))
            with SessionLocal() as db:
                ev = db.get(ProcessingEvent, eid)
                ev.Stage_Status, ev.Completed_At, ev.Duration = status, datetime.utcnow(), dur
                ev.Output_Summary, ev.Error_Message = _short(summary), err
                db.commit()
            return out
        return wrapper
    return deco
