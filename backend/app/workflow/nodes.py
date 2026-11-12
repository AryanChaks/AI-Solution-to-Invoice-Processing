"""LangGraph nodes. Each is a thin orchestrator over deterministic services; the LLM only appears in n_structured
and can never touch the database or the decision."""
import hashlib, os, re
from datetime import datetime
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from PIL import Image
from ..config import settings
from ..database.connection import SessionLocal
from ..database.models import (Invoice, ProcessingRun, ExtractionEvidence, PurchaseOrder, Vendor)
from ..extraction.normalizer import normalize_invoice_number, parse_amount, parse_date
from ..extraction import pdf_extractor, field_extractor
from ..extraction.ocr_service import OCRUnavailable
from ..extraction.llm_extractor import llm_extract
from ..matching.duplicate_detector import ExistingInvoice, classify
from ..matching.po_matcher import hard_checks, price_check, po_consumption, rank_candidates
from ..services import po_service, payment_service, invoice_service
from ..services.common import audit, jdump
from ..services.settings_service import get_policy
from ..services.vendor_service import resolve_vendor, vendor_known_in_text
from ..validation.financial_validator import Line, reconcile, reconcile_header
from ..validation.rule_engine import Facts, decide
from .events import stage
from .state import InvoiceState

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
CRITICAL = ["invoice_number", "invoice_date", "total"]

def _f(state, code, sev, msg):
    state.setdefault("findings", []).append({"code": code, "severity": sev, "message": msg})

def _add(state, fl):
    for f in fl:
        _f(state, f.code, f.severity, f.message)

@stage("n_receive")
def n_receive(s: InvoiceState):
    return {"_summary": f"Source={s['source']} file={s.get('file_name') or '-'}", "findings": []}

@stage("n_validate_file")
def n_validate_file(s):
    p = s["file_path"]
    ext = os.path.splitext(p)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported file type {ext}")
    size = os.path.getsize(p)
    if size == 0 or size > settings.max_upload_size_mb * 1024 * 1024:
        raise ValueError(f"File size {size} bytes outside limits")
    with open(p, "rb") as fh:
        head = fh.read(8); fh.seek(0); h = hashlib.sha256(fh.read()).hexdigest()
    if ext == ".pdf" and not head.startswith(b"%PDF"):
        raise ValueError("File is not a valid PDF (bad signature)")
    if ext != ".pdf":
        Image.open(p).verify()
    return {"file_hash": h, "_summary": f"{ext} OK, {size} bytes, sha256={h[:12]}…"}

@stage("n_inspect")
def n_inspect(s):
    if s["file_path"].lower().endswith(".pdf"):
        info = pdf_extractor.inspect_pdf(s["file_path"])
    else:
        info = {"pages": 1, "doc_type": "IMAGE", "scanned_pages": [0], "chars": [0]}
    return {"inspect": info, "doc_type": info["doc_type"],
            "_summary": f"{info['doc_type']} document, {info['pages']} page(s); OCR pages: {[p+1 for p in info['scanned_pages']] or 'none'}"}

@stage("n_extract_text")
def n_extract_text(s):
    try:
        r = pdf_extractor.extract_pdf(s["file_path"], s["inspect"]) if s["doc_type"] != "IMAGE" else pdf_extractor.extract_image(s["file_path"])
    except OCRUnavailable as e:
        return {"extraction_failed": True, "_status": "REVIEW_REQUIRED", "_summary": str(e), "words": [], "page_texts": []}
    total = sum(len(t) for t in r["page_texts"])
    if total < 30:
        return {**r, "extraction_failed": True, "_status": "REVIEW_REQUIRED", "_summary": "No readable text could be extracted."}
    conf = f", mean OCR confidence {r['avg_ocr_conf']:.0%}" if r["avg_ocr_conf"] is not None else ""
    return {**r, "extraction_failed": False, "_summary": f"{total} chars extracted ({'OCR' if r['ocr_pages'] else 'embedded text'}, no OCR needed for digital pages){conf}"}

@stage("n_structured")
def n_structured(s):
    ex = field_extractor.extract_fields(s["page_texts"], s["words"], s["tables"], s["ocr_pages"], s["avg_ocr_conf"])
    fields, lines = ex["fields"], ex["lines"]
    text = "\n".join(s["page_texts"])
    with SessionLocal() as db:
        v = vendor_known_in_text(db, text)
        vname = v.Vendor_Name if v else None
    gstins = ex["gstins"]
    if vname:
        loc = field_extractor.locate(s["words"], vname.split()[0]) if s["words"] else None
        fields["vendor_name"] = {"value": vname, "confidence": 0.95 if not s["ocr_pages"] else 0.85,
                                 "page": loc[0] if loc else None, "bbox": loc[1] if loc else None,
                                 "method": "REGISTRY_TEXT_MATCH", "validation": "VALID"}
    used_llm = False
    if any(k not in fields for k in ("invoice_number", "total", "invoice_date")) or not lines or "vendor_name" not in fields:
        llm = llm_extract(text)
        if llm:
            used_llm = True
            for k, val in llm["fields"].items():
                if k not in fields:
                    loc = field_extractor.locate(s["words"], val)
                    fields[k] = {"value": val, "confidence": 0.7, "page": loc[0] if loc else None,
                                 "bbox": loc[1] if loc else None, "method": "LLM_GROUNDED", "validation": "UNVERIFIED"}
            if not lines:
                lines = llm["lines"]
    if "vendor_name" not in fields:
        first = next((l.strip() for l in s["page_texts"][0].splitlines() if re.search(r"[A-Za-z]{3}", l)), None)
        if first:
            fields["vendor_name"] = {"value": first, "confidence": 0.4, "page": 1, "bbox": None,
                                     "method": "FIRST_LINE_GUESS", "validation": "UNVERIFIED"}
    raw = {"invoice": {k: v["value"] for k, v in fields.items() if k != "vendor_name"} | ({"vendor_name": fields["vendor_name"]["value"]} if "vendor_name" in fields else {}),
           "lines": lines, "gstins": gstins}
    return {"raw": raw, "evidence": fields,
            "_summary": f"{len(fields)} fields, {len(lines)} line item(s), LLM {'used' if used_llm else 'not used'}"}

@stage("n_normalize")
def n_normalize(s):
    raw = s.get("raw", {})
    r = raw.get("invoice", {})
    errors, inferred = [], []
    inv = {"invoice_number": (r.get("invoice_number") or "").strip() or None, "vendor_name": r.get("vendor_name"),
           "po_number": (r.get("po_number") or "").strip() or None, "notes": r.get("notes")}
    inv["norm_number"] = normalize_invoice_number(inv["invoice_number"])
    for k in ("invoice_date", "due_date"):
        inv[k] = parse_date(r.get(k)) if r.get(k) else None
        if r.get(k) and inv[k] is None: errors.append(f"{k} '{r.get(k)}' unparseable")
    for k in ("subtotal", "tax", "discount", "other", "total"):
        inv[k] = parse_amount(r.get(k)) if r.get(k) not in (None, "") else None
        if r.get(k) not in (None, "") and inv[k] is None: errors.append(f"{k} '{r.get(k)}' unparseable")
    inv["discount"] = inv["discount"] or Decimal(0); inv["other"] = inv["other"] or Decimal(0)
    cur = (r.get("currency") or "").strip().upper()
    if not cur:
        cur = "INR"; inferred.append("currency")
    inv["currency"] = cur
    lines = []
    for i, l in enumerate(raw.get("lines", []), 1):
        q, p = parse_amount(l.get("quantity")), parse_amount(l.get("unit_price"))
        if q is None or p is None or not l.get("description"):
            errors.append(f"line {i} incomplete (needs description, quantity, unit price)"); continue
        lines.append({"description": l["description"], "item_code": l.get("item_code") or None, "quantity": q, "unit_price": p,
                      "tax_rate": parse_amount(l.get("tax_rate")) or Decimal(0),
                      "line_total": parse_amount(l.get("line_total")) if l.get("line_total") else None})
    inv["lines"] = lines
    pay = raw.get("payment")
    payment = None
    if pay and (pay.get("amount") or pay.get("ref")):
        payment = {"amount": parse_amount(pay.get("amount")), "date": parse_date(pay.get("date")) if pay.get("date") else None,
                   "method": pay.get("method") or ("UPI" if pay.get("ref") else None), "ref": pay.get("ref"),
                   "image_amount": parse_amount(pay.get("image_amount")) if pay.get("image_amount") else None,
                   "source": pay.get("source", "MANUAL")}
    ev = dict(s.get("evidence") or {})
    if s["source"] in ("MANUAL", "EXCEL") or s.get("skip_extraction"):
        for k, v in r.items():
            if v not in (None, "") and k not in ev:
                ev[k] = {"value": str(v), "confidence": 1.0, "page": None, "bbox": None,
                         "method": s["source"], "validation": "VALID"}
    for k in inferred:
        if k in ev: pass
        else: ev[k] = {"value": cur, "confidence": 0.5, "page": None, "bbox": None, "method": "INFERRED_DEFAULT", "validation": "UNVERIFIED"}
    return {"invoice": inv, "payment": payment, "evidence": ev,
            "_status": "REVIEW_REQUIRED" if errors else "COMPLETED",
            "_summary": ("Parse problems: " + "; ".join(errors)) if errors else
                        f"Normalised: no. {inv['norm_number'] or '—'}, total {inv['total']}, {len(lines)} line(s)"
                        + (f"; inferred {inferred}" if inferred else "")} | ({"findings": s.get("findings", []) + [{"code": "PARSE_ERROR", "severity": "ERROR", "message": e} for e in errors]} if errors else {})

@stage("n_required")
def n_required(s):
    inv, ev = s["invoice"], s.get("evidence", {})
    with SessionLocal() as db:
        policy = get_policy(db)
        missing = [k for k in CRITICAL if inv.get(k) in (None, "")]
        low = [k for k in CRITICAL + ["vendor_name"] if k in ev and (ev[k].get("validation") == "INVALID"
               or Decimal(str(ev[k]["confidence"])) < policy.min_field_confidence) and not ev[k].get("corrected")]
        for name, e in ev.items():
            db.add(ExtractionEvidence(Run_ID=s["run_id"], Field_Name=name, Extracted_Value=str(e.get("value")),
                Corrected_Value=e.get("corrected_value"), Confidence_Score=Decimal(str(e["confidence"])), Source_Page=e.get("page"),
                Bounding_Box=",".join(f"{x:.1f}" for x in e["bbox"]) if e.get("bbox") else None,
                Extraction_Method=e.get("method"), Validation_Status=e.get("validation"), Is_Manually_Corrected=bool(e.get("corrected"))))
        db.commit()
    for m in missing:
        _f(s, "MISSING_FIELD", "ERROR", f"Required field '{m}' missing")
    for l in low:
        _f(s, "LOW_CONFIDENCE", "ERROR", f"Field '{l}' has low/invalid extraction confidence")
    return {"missing": missing, "low_conf": low, "findings": s.get("findings", []),
            "_status": "REVIEW_REQUIRED" if (missing or low) else "COMPLETED",
            "_summary": f"Missing: {missing or 'none'}; low confidence: {low or 'none'}"}

@stage("n_vendor")
def n_vendor(s):
    raw = s.get("raw", {})
    with SessionLocal() as db:
        v, why = None, "No registered vendor matched"
        v, why = resolve_vendor(db, vendor_id=raw.get("vendor_id")) if raw.get("vendor_id") else (None, why)
        if not v:
            for g in raw.get("gstins", []) or []:
                v, why = resolve_vendor(db, gstin=g)
                if v: break
        if not v:
            v, why = resolve_vendor(db, name=s["invoice"].get("vendor_name"))
        if not v:
            _f(s, "VENDOR_UNKNOWN", "ERROR", why)
            return {"vendor_id": None, "vendor_approved": False, "vendor_reason": why, "findings": s["findings"],
                    "_status": "REVIEW_REQUIRED", "_summary": why}
        if not v.Is_Active or not v.Is_Approved:
            _f(s, "VENDOR_UNAPPROVED", "ERROR", f"Vendor {v.Vendor_Name} is {'inactive' if not v.Is_Active else 'not approved'}")
        return {"vendor_id": v.Vendor_ID, "vendor_name": v.Vendor_Name, "vendor_approved": bool(v.Is_Approved and v.Is_Active),
                "vendor_reason": why, "findings": s["findings"],
                "_status": "COMPLETED" if (v.Is_Approved and v.Is_Active) else "REVIEW_REQUIRED",
                "_summary": f"{v.Vendor_Name} — {why}; approved={v.Is_Approved}"}

@stage("n_identify")
def n_identify(s):
    inv, vid, h, tgt = s["invoice"], s.get("vendor_id"), s.get("file_hash"), s.get("reprocess_invoice_id")
    with SessionLocal() as db:
        ids = set()
        if vid: ids |= {i.Invoice_ID for i in db.query(Invoice).filter(Invoice.Vendor_ID == vid)}
        if h and not tgt: ids |= {r.Invoice_ID for r in db.query(ProcessingRun).filter(ProcessingRun.File_Hash == h, ProcessingRun.Invoice_ID.isnot(None))}
        ex = []
        for i in db.query(Invoice).filter(Invoice.Invoice_ID.in_(ids)).all() if ids else []:
            hashes = [r.File_Hash for r in db.query(ProcessingRun).filter(ProcessingRun.Invoice_ID == i.Invoice_ID) if r.File_Hash]
            ex.append(ExistingInvoice(i.Invoice_ID, i.Vendor_ID, i.Normalized_Invoice_Number, i.Invoice_Date, i.Total_Amount, hashes))
    d = classify(vid, inv["norm_number"], inv["invoice_date"], inv["total"], None if tgt else h, ex)
    out = {"outcome": d.outcome, "invoice_id": d.invoice_id, "reasons": d.reasons}
    if tgt and d.invoice_id in (None, tgt):   # reviewer-initiated reprocess always updates the SAME invoice
        out = {"outcome": "EXISTING_UPDATE", "invoice_id": tgt, "reasons": [f"Reprocess after manual correction of invoice #{tgt}"]}
    if out["outcome"] in ("CONFIRMED_DUPLICATE", "POTENTIAL_DUPLICATE"):
        _f(s, "DUPLICATE", "ERROR", f"{out['outcome']} of invoice #{out['invoice_id']}: " + "; ".join(out["reasons"]))
    skip = out["outcome"] == "CONFIRMED_DUPLICATE"
    return {"dup": out, "target_invoice_id": out["invoice_id"] if out["outcome"] == "EXISTING_UPDATE" else None, "findings": s["findings"],
            "_status": "REVIEW_REQUIRED" if out["outcome"] in ("CONFIRMED_DUPLICATE", "POTENTIAL_DUPLICATE") else "COMPLETED",
            "_summary": f"{out['outcome']}" + (f" (invoice #{out['invoice_id']})" if out["invoice_id"] else "") + ": " + "; ".join(out["reasons"])
                        + ("  → BRANCH: skipping PO matching/reconciliation" if skip else "")}

@stage("n_po_match")
def n_po_match(s):
    inv, vid, raw = s["invoice"], s.get("vendor_id"), s.get("raw", {})
    with SessionLocal() as db:
        po, cands, ambiguous, how = None, [], False, ""
        if raw.get("po_id"):
            po, how = db.get(PurchaseOrder, int(raw["po_id"])), "manually selected PO"
        elif inv.get("po_number"):
            po = po_service.find_by_number(db, inv["po_number"]); how = f"explicit reference {inv['po_number']}"
            if not po: _f(s, "PO_REF_UNKNOWN", "ERROR", f"PO reference '{inv['po_number']}' not found in system")
        elif vid:
            lines = [Line(l["description"], l["quantity"], l["unit_price"], item_code=l.get("item_code")) for l in inv["lines"]]
            pos = [po_service.to_info(p) for p in db.query(PurchaseOrder).filter(PurchaseOrder.Vendor_ID == vid)]
            ranked = rank_candidates(pos, vid, inv["currency"], lines, inv["total"])
            nums = {p.PO_ID: p.PO_Number for p in db.query(PurchaseOrder).filter(PurchaseOrder.Vendor_ID == vid)}
            cands = [{**c, "po_number": nums[c["po_id"]]} for c in ranked[:3]]
            if ranked and ranked[0]["score"] >= 60 and (len(ranked) == 1 or ranked[0]["score"] - ranked[1]["score"] >= 15):
                po, how = db.get(PurchaseOrder, ranked[0]["po_id"]), f"inferred from content (score {ranked[0]['score']})"
            elif ranked:
                ambiguous = True; _f(s, "PO_AMBIGUOUS", "ERROR", "No explicit PO reference; candidates are ambiguous")
            else:
                _f(s, "PO_NOT_FOUND", "ERROR", "No PO reference and no candidate PO for this vendor")
        else:
            _f(s, "PO_NOT_FOUND", "ERROR", "No PO reference on invoice")
        info = None
        if po:
            info = {"po_id": po.PO_ID, "po_number": po.PO_Number, "total": po.PO_Total_Amount, "currency": po.Currency,
                    "status": po.PO_Status, "vendor_id": po.Vendor_ID, "how": how}
            if vid: _add(s, hard_checks(po_service.to_info(po), vid, inv["currency"]))
            if inv.get("invoice_date") and po.PO_Date > inv["invoice_date"]:
                _f(s, "INVOICE_BEFORE_PO", "WARNING", "Invoice is dated before the PO")
        bad = po is None
    return {"po": info, "po_ambiguous": ambiguous, "candidates": cands, "findings": s["findings"],
            "_status": "REVIEW_REQUIRED" if bad else "COMPLETED",
            "_summary": f"PO {info['po_number']} via {how}" if info else ("Ambiguous: " + ", ".join(f"{c['po_number']}({c['score']})" for c in cands) if ambiguous else "No PO matched")}

@stage("n_reconcile")
def n_reconcile(s):
    inv = s["invoice"]
    with SessionLocal() as db:
        policy = get_policy(db)
        if inv["lines"]:
            lines = [Line(l["description"], l["quantity"], l["unit_price"], l["tax_rate"], l["line_total"], l["item_code"]) for l in inv["lines"]]
            r = reconcile(lines, inv["total"], inv["tax"], inv["discount"], inv["other"], policy)
            if s.get("po"):
                po = db.get(PurchaseOrder, s["po"]["po_id"])
                _add(s, price_check(po_service.to_info(po), lines, policy))
        else:
            r = reconcile_header(inv.get("subtotal"), inv.get("tax"), inv["discount"], inv["other"], inv["total"], policy,
                                 "WARNING" if s["source"] == "EXCEL" else "ERROR")
        _add(s, r.findings)
    return {"recon": {"steps": r.steps, "expected_total": str(r.expected_total), "difference": str(r.difference),
                      "calc_subtotal": str(r.calc_subtotal), "calc_tax": str(r.calc_tax)},
            "findings": s["findings"], "_status": "COMPLETED" if r.ok else "REVIEW_REQUIRED",
            "_summary": f"Expected {r.expected_total} vs stated {r.stated_total} (Δ {r.difference}); " + (", ".join(f.code for f in r.findings) or "all checks passed")}

@stage("n_po_consumption")
def n_po_consumption(s):
    if not s.get("po"):
        return {"_summary": "No PO: consumption check skipped", "consumption": {}}
    with SessionLocal() as db:
        c = po_consumption(s["po"]["total"], po_service.prior_invoices(db, s["po"]["po_id"], s.get("target_invoice_id")),
                           s["invoice"]["total"], get_policy(db))
    _add(s, c["findings"])
    cons = {k: str(v) for k, v in c.items() if k != "findings"}
    return {"consumption": cons, "findings": s["findings"], "_status": "REVIEW_REQUIRED" if c["findings"] else "COMPLETED",
            "_summary": f"PO {cons['po_total']}; invoiced before {cons['invoiced_before']}; remaining {cons['remaining_before']} → after {cons['remaining_after']}"}

@stage("n_rules")
def n_rules(s):
    from ..validation.financial_validator import Finding
    inv = s.get("invoice") or {}
    f = Facts(invoice_number=inv.get("invoice_number"), invoice_date=inv.get("invoice_date"), total=inv.get("total"),
              vendor_resolved=bool(s.get("vendor_id")), vendor_approved=bool(s.get("vendor_approved")),
              po_found=bool(s.get("po")), po_ambiguous=bool(s.get("po_ambiguous")),
              dup_outcome=(s.get("dup") or {}).get("outcome", "NEW"), extraction_failed=bool(s.get("extraction_failed")),
              low_confidence_fields=s.get("low_conf", []),
              findings=[Finding(**x) for x in s.get("findings", []) if x["code"] not in ("LOW_CONFIDENCE",)])
    d = decide(f)
    dd = {"status": d.status, "passed": d.passed, "failed": d.failed, "warnings": d.warnings,
          "explanation": d.explanation, "next_action": d.next_action}
    return {"decision": dd, "_status": "COMPLETED" if d.status == "AUTO_APPROVED_FOR_AP" else "REVIEW_REQUIRED",
            "_summary": d.explanation}

@stage("n_persist")
def n_persist(s):
    d, inv, dup = dict(s["decision"]), s.get("invoice") or {}, s.get("dup") or {}
    vid = s.get("vendor_id")
    resolvable = bool(vid and inv.get("norm_number") and inv.get("total") is not None)
    notes, invoice_id, pay_err = [], None, None
    with SessionLocal() as db:
        try:
            if not resolvable:
                db.rollback()
                return {"invoice_id": None, "_status": "REVIEW_REQUIRED",
                        "_summary": "Invoice identity not resolved (vendor/number/total) — nothing written to Invoices; extracted data kept for review"}
            po_id = s["po"]["po_id"] if s.get("po") else None
            # Re-check PO consumption INSIDE the transaction under lock so concurrent runs cannot over-consume silently.
            if po_id and d["status"] == "AUTO_APPROVED_FOR_AP":
                c = po_consumption(s["po"]["total"], po_service.prior_invoices(db, po_id, s.get("target_invoice_id"), lock=True),
                                   inv["total"], get_policy(db))
                if c["findings"]:
                    d["status"] = "REVIEW_REQUIRED"; d["failed"] = d["failed"] + ["PO_OVERRUN (re-check at commit): " + c["findings"][0].message]
                    d["explanation"] += " PO capacity changed during processing; downgraded to review."
                    notes.append("PO re-check downgraded decision")
            outcome = dup.get("outcome", "NEW")
            if outcome == "CONFIRMED_DUPLICATE":
                invoice_id = dup["invoice_id"]; notes.append(f"Duplicate of invoice #{invoice_id}; no invoice written")
            elif outcome == "EXISTING_UPDATE":
                invoice_id = dup["invoice_id"]
                ex = db.get(Invoice, invoice_id)
                ok, conflict = invoice_service.update_invoice(db, ex, inv, vid, po_id, s["source"], d["status"], d["status"],
                                                              reviewer_initiated=bool(s.get("reprocess_invoice_id")))
                if not ok:
                    d["status"] = "REVIEW_REQUIRED"; d["failed"] = d["failed"] + ["UPDATE_CONFLICT: " + conflict]
                    d["explanation"] += " Conflicting values for an approved invoice were NOT applied."
                    d["next_action"] = "Reviewer must decide whether the revised values should replace the approved record."
                notes.append("Existing invoice updated" if ok else "Conflict: approved invoice left untouched")
            else:
                try:
                    with db.begin_nested():
                        created = invoice_service.create_invoice(db, inv, vid, po_id, s["source"], d["status"], d["status"])
                    invoice_id = created.Invoice_ID; notes.append(f"Invoice #{invoice_id} created")
                except IntegrityError:   # concurrent insert of same vendor+number
                    ex = db.query(Invoice).filter_by(Vendor_ID=vid, Normalized_Invoice_Number=inv["norm_number"]).first()
                    invoice_id = ex.Invoice_ID; d["status"] = "BLOCKED"; d["failed"].append("Confirmed duplicate (concurrent insert)")
                    notes.append("Concurrent duplicate resolved to existing invoice")
            pay = s.get("payment")
            if pay and invoice_id:
                try:
                    with db.begin_nested():
                        payment_service.add_payment(db, db.get(Invoice, invoice_id), pay["amount"], pay["date"], pay["method"],
                                                    pay["ref"], pay.get("source", "MANUAL"), pay.get("image_amount"))
                    notes.append("Payment recorded")
                except payment_service.PaymentError as e:
                    pay_err = str(e); notes.append("Payment NOT recorded: " + pay_err)
            audit(db, "Invoice", invoice_id, "PROCESSED", new={"decision": d["status"], "run": s["run_id"]}, reason="; ".join(notes))
            db.commit()
        except Exception:
            db.rollback(); raise
    return {"invoice_id": invoice_id, "decision": d, "payment_error": pay_err,
            "_status": "COMPLETED", "_summary": "; ".join(notes)}

@stage("n_route")
def n_route(s):
    st = s["decision"]["status"]
    with SessionLocal() as db:
        run = db.get(ProcessingRun, s["run_id"])
        if st in ("REVIEW_REQUIRED", "BLOCKED"):
            run.Review_Status = "PENDING"
        db.commit()
    return {"_status": "REVIEW_REQUIRED" if st != "AUTO_APPROVED_FOR_AP" else "COMPLETED",
            "_summary": "Added to Review Queue" if st in ("REVIEW_REQUIRED", "BLOCKED") else "No review needed"}

def n_fail(s):
    return {"decision": {"status": "FAILED", "passed": [], "failed": [s.get("error", "unknown")], "warnings": [],
                         "explanation": "Technical failure: " + str(s.get("error")), "next_action": "Fix the cause and reprocess."}}
