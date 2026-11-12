import json, logging, time
from datetime import datetime
from decimal import Decimal
from langgraph.graph import StateGraph, START, END
from ..database.connection import SessionLocal
from ..database.models import ProcessingRun
from ..services.common import jdump
from . import nodes as N
from .state import InvoiceState

log = logging.getLogger(__name__)

def _go(nxt):
    return lambda s: "fail" if s.get("error") else nxt

def build_graph():
    g = StateGraph(InvoiceState)
    for name in ["n_receive", "n_validate_file", "n_inspect", "n_extract_text", "n_structured", "n_normalize", "n_required",
                 "n_vendor", "n_identify", "n_po_match", "n_reconcile", "n_po_consumption", "n_rules", "n_persist", "n_route", "n_fail"]:
        g.add_node(name, getattr(N, name))
    g.add_edge(START, "n_receive")

    def after_receive(s):
        if s.get("error"): return "fail"
        return "n_validate_file" if (s["source"] in ("PDF", "IMAGE") and not s.get("skip_extraction")) else "n_normalize"
    g.add_conditional_edges("n_receive", after_receive, {"fail": "n_fail", "n_validate_file": "n_validate_file", "n_normalize": "n_normalize"})
    for a, b in [("n_validate_file", "n_inspect"), ("n_inspect", "n_extract_text"), ("n_structured", "n_normalize"),
                 ("n_normalize", "n_required"), ("n_vendor", "n_identify"), ("n_po_match", "n_reconcile"),
                 ("n_reconcile", "n_po_consumption"), ("n_po_consumption", "n_rules"), ("n_rules", "n_persist"),
                 ("n_persist", "n_route")]:
        g.add_conditional_edges(a, _go(b), {"fail": "n_fail", b: b})
    # BRANCH: extraction failed -> straight to decision (manual review)
    g.add_conditional_edges("n_extract_text", lambda s: "fail" if s.get("error") else ("n_rules" if s.get("extraction_failed") else "n_structured"),
                            {"fail": "n_fail", "n_rules": "n_rules", "n_structured": "n_structured"})
    # BRANCH: missing critical fields -> decision
    g.add_conditional_edges("n_required", lambda s: "fail" if s.get("error") else ("n_rules" if (
        not s["invoice"].get("invoice_number") or s["invoice"].get("total") is None) else "n_vendor"),
        {"fail": "n_fail", "n_rules": "n_rules", "n_vendor": "n_vendor"})
    # BRANCH: confirmed duplicate -> decision (skip PO matching / reconciliation)
    g.add_conditional_edges("n_identify", lambda s: "fail" if s.get("error") else ("n_rules" if s["dup"]["outcome"] == "CONFIRMED_DUPLICATE" else "n_po_match"),
                            {"fail": "n_fail", "n_rules": "n_rules", "n_po_match": "n_po_match"})
    g.add_edge("n_route", END)
    g.add_edge("n_fail", END)
    return g.compile()

_GRAPH = None
def graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH

def run_workflow(run_id: int, state: dict):
    """Executes the graph and records the final outcome on Processing_Runs. Never raises."""
    t0 = time.perf_counter()
    state = {**state, "run_id": run_id}
    try:
        final = graph().invoke(state)
    except Exception as e:
        log.exception("Graph crashed")
        final = {**state, "error": str(e), "decision": {"status": "FAILED", "explanation": str(e), "failed": [str(e)], "passed": [], "warnings": [], "next_action": "Reprocess"}}
    d = final.get("decision", {})
    detail = {"decision": d, "findings": final.get("findings", []), "dup": final.get("dup"), "po": final.get("po"),
              "candidates": final.get("candidates"), "consumption": final.get("consumption"), "recon": final.get("recon"),
              "vendor": {"id": final.get("vendor_id"), "name": final.get("vendor_name"), "reason": final.get("vendor_reason")},
              "payment_error": final.get("payment_error"), "missing": final.get("missing"), "low_conf": final.get("low_conf")}
    with SessionLocal() as db:
        run = db.get(ProcessingRun, run_id)
        run.Invoice_ID = final.get("invoice_id")
        run.Final_Decision = d.get("status")
        run.Processing_Status = "FAILED" if d.get("status") == "FAILED" else "COMPLETED"
        run.Completed_At = datetime.utcnow()
        run.Processing_Duration = Decimal(str(round(time.perf_counter() - t0, 3)))
        run.File_Hash = final.get("file_hash") or run.File_Hash
        run.Doc_Type = final.get("doc_type")
        run.Decision_Json = jdump(detail)
        run.Parsed_Json = jdump(final.get("raw") or state.get("raw") or {})
        if d.get("status") == "FAILED" and not run.Review_Status:
            run.Review_Status = None
        db.commit()
