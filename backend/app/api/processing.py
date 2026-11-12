import asyncio, json, os
from datetime import datetime, timedelta
from typing import Optional
import fitz
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from ..database.connection import get_db, SessionLocal
from ..database.models import ProcessingRun, ProcessingEvent, Invoice, Vendor, ExtractionEvidence
from ..schemas.models import ReprocessIn
from ..services.common import audit
from ..utils.runs import create_run, start_background, jl, row
from ..workflow.events import STAGES

router = APIRouter(prefix="/api/processing", tags=["processing"])

def _summary(r: ProcessingRun, db):
    inv = db.get(Invoice, r.Invoice_ID) if r.Invoice_ID else None
    vname = db.get(Vendor, inv.Vendor_ID).Vendor_Name if inv else None
    parsed = jl(r.Parsed_Json) or {}
    p_inv = parsed.get("invoice", {}) if isinstance(parsed, dict) else {}
    dec = (jl(r.Decision_Json) or {})
    return {**row(r, ("Decision_Json", "Parsed_Json")), "Invoice_Number": inv.Invoice_Number if inv else p_inv.get("invoice_number"),
            "Vendor_Name": vname or (dec.get("vendor") or {}).get("name") or p_inv.get("vendor_name"),
            "Total_Amount": inv.Total_Amount if inv else p_inv.get("total")}

@router.get("/stages")
def stages():
    return [{"name": n, "label": l} for n, l in STAGES]

@router.get("/runs")
def runs(vendor_id: Optional[int] = None, decision: Optional[str] = None, source: Optional[str] = None,
         status: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
         limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    q = db.query(ProcessingRun)
    if decision: q = q.filter(ProcessingRun.Final_Decision == decision)
    if source: q = q.filter(ProcessingRun.Source_Type == source)
    if status: q = q.filter(ProcessingRun.Processing_Status == status)
    if date_from: q = q.filter(ProcessingRun.Started_At >= datetime.fromisoformat(date_from))
    if date_to: q = q.filter(ProcessingRun.Started_At < datetime.fromisoformat(date_to) + timedelta(days=1))
    out = [_summary(r, db) for r in q.order_by(ProcessingRun.Run_ID.desc()).limit(limit)]
    if vendor_id:
        v = db.get(Vendor, vendor_id)
        out = [o for o in out if v and o["Vendor_Name"] == v.Vendor_Name]
    return out

@router.get("/runs/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db)):
    r = db.get(ProcessingRun, run_id)
    if not r: raise HTTPException(404, "Run not found")
    return {**_summary(r, db), "detail": jl(r.Decision_Json), "parsed": jl(r.Parsed_Json),
            "evidence": [row(e) for e in db.query(ExtractionEvidence).filter_by(Run_ID=run_id)],
            "events": [row(e) for e in db.query(ProcessingEvent).filter_by(Run_ID=run_id).order_by(ProcessingEvent.Event_ID)],
            "has_file": bool(r.Stored_File_Path and os.path.exists(r.Stored_File_Path))}

@router.get("/runs/{run_id}/events")
def events(run_id: int, db: Session = Depends(get_db)):
    return [row(e) for e in db.query(ProcessingEvent).filter_by(Run_ID=run_id).order_by(ProcessingEvent.Event_ID)]

@router.get("/runs/{run_id}/stream")
async def stream(run_id: int):
    """SSE: emits an event whenever a persisted Processing_Events row is created/changes status. Reconnect-safe
    (state is re-read from the DB, so a late client simply receives the history first)."""
    def snapshot():
        with SessionLocal() as db:
            r = db.get(ProcessingRun, run_id)
            if not r: return None
            evs = [row(e) for e in db.query(ProcessingEvent).filter_by(Run_ID=run_id).order_by(ProcessingEvent.Event_ID)]
            return evs, r.Processing_Status, r.Final_Decision, r.Invoice_ID

    async def gen():
        seen = {}
        while True:
            snap = await asyncio.to_thread(snapshot)
            if snap is None:
                yield {"event": "error", "data": json.dumps({"message": "run not found"})}; return
            evs, pstatus, decision, inv_id = snap
            for e in evs:
                key = (e["Event_ID"], e["Stage_Status"])
                if seen.get(e["Event_ID"]) != key:
                    seen[e["Event_ID"]] = key
                    yield {"event": "stage", "data": json.dumps(e, default=str)}
            if pstatus != "RUNNING":
                yield {"event": "done", "data": json.dumps({"status": pstatus, "decision": decision, "invoice_id": inv_id})}
                return
            await asyncio.sleep(0.4)
    return EventSourceResponse(gen())

@router.post("/runs/{run_id}/reprocess")
def reprocess(run_id: int, b: ReprocessIn, db: Session = Depends(get_db)):
    return do_reprocess(db, run_id, b.corrections, b.reason or "Reprocess")

def do_reprocess(db, run_id, corrections: dict, reason: str, actor="local-user"):
    old = db.get(ProcessingRun, run_id)
    if not old: raise HTTPException(404, "Run not found")
    parsed = jl(old.Parsed_Json) or {"invoice": {}, "lines": [], "gstins": []}
    raw = {"invoice": dict(parsed.get("invoice", {})), "lines": parsed.get("lines", []), "gstins": parsed.get("gstins", []),
           "vendor_id": parsed.get("vendor_id"), "po_id": parsed.get("po_id"), "payment": parsed.get("payment")}
    ev = {}
    for e in db.query(ExtractionEvidence).filter_by(Run_ID=run_id):
        ev[e.Field_Name] = {"value": e.Corrected_Value or e.Extracted_Value, "confidence": float(e.Confidence_Score or 0),
                            "page": e.Source_Page, "bbox": [float(x) for x in e.Bounding_Box.split(",")] if e.Bounding_Box else None,
                            "method": e.Extraction_Method, "validation": e.Validation_Status, "corrected": e.Is_Manually_Corrected,
                            "corrected_value": e.Corrected_Value}
    changed = {}
    for k, v in corrections.items():
        if k in ("vendor_id", "po_id", "payment"):
            raw[k] = v; changed[k] = v; continue
        if k == "lines":
            raw["lines"] = v; changed[k] = "lines replaced"; continue
        old_v = raw["invoice"].get(k)
        raw["invoice"][k] = v; changed[k] = {"old": old_v, "new": v}
        ev[k] = {"value": str(old_v) if old_v is not None else "", "confidence": 1.0, "page": ev.get(k, {}).get("page"),
                 "bbox": ev.get(k, {}).get("bbox"), "method": "MANUAL_CORRECTION", "validation": "VALID",
                 "corrected": True, "corrected_value": str(v)}
    has_file = bool(old.Stored_File_Path and os.path.exists(old.Stored_File_Path))
    full_rerun = (not corrections) and has_file and old.Source_Type in ("PDF", "IMAGE")
    new = create_run(db, old.Source_Type, old.Uploaded_File_Name, old.Stored_File_Path, old.File_Hash, parent=run_id)
    if changed:
        audit(db, "Invoice" if old.Invoice_ID else "Run", old.Invoice_ID or run_id, "FIELD_CORRECTION",
              old={k: (v.get("old") if isinstance(v, dict) else None) for k, v in changed.items()}, new=changed, reason=reason, actor=actor)
    audit(db, "Run", run_id, "REPROCESS", new={"new_run": new.Run_ID}, reason=reason, actor=actor)
    old.Review_Status = "SUPERSEDED"
    db.commit()
    state = {"source": old.Source_Type, "file_path": old.Stored_File_Path, "file_name": old.Uploaded_File_Name,
             "file_hash": old.File_Hash, "reprocess_invoice_id": old.Invoice_ID}
    if full_rerun:
        state["skip_extraction"] = False
    else:
        state.update(skip_extraction=True, raw=raw, evidence=ev, doc_type=old.Doc_Type or "")
    start_background(new.Run_ID, state)
    return {"run_id": new.Run_ID}

# ---------- original document viewer ----------
@router.get("/runs/{run_id}/file")
def original_file(run_id: int, db: Session = Depends(get_db)):
    r = db.get(ProcessingRun, run_id)
    if not r or not r.Stored_File_Path or not os.path.exists(r.Stored_File_Path):
        raise HTTPException(404, "Original file not available")
    return FileResponse(r.Stored_File_Path, filename=r.Uploaded_File_Name)

@router.get("/runs/{run_id}/pages")
def pages(run_id: int, db: Session = Depends(get_db)):
    r = db.get(ProcessingRun, run_id)
    if not r or not r.Stored_File_Path or not os.path.exists(r.Stored_File_Path):
        raise HTTPException(404, "Original file not available")
    if not r.Stored_File_Path.lower().endswith(".pdf"):
        from PIL import Image
        im = Image.open(r.Stored_File_Path)
        return [{"page": 1, "width": im.width * 72 / 200, "height": im.height * 72 / 200}]
    with fitz.open(r.Stored_File_Path) as d:
        return [{"page": i + 1, "width": p.rect.width, "height": p.rect.height} for i, p in enumerate(d)]

@router.get("/runs/{run_id}/page/{n}.png")
def page_png(run_id: int, n: int, db: Session = Depends(get_db)):
    r = db.get(ProcessingRun, run_id)
    if not r or not r.Stored_File_Path or not os.path.exists(r.Stored_File_Path):
        raise HTTPException(404, "Original file not available")
    if not r.Stored_File_Path.lower().endswith(".pdf"):
        return FileResponse(r.Stored_File_Path)
    with fitz.open(r.Stored_File_Path) as d:
        if not 1 <= n <= d.page_count: raise HTTPException(404, "No such page")
        return Response(d[n - 1].get_pixmap(dpi=144).tobytes("png"), media_type="image/png")
