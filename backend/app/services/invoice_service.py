"""Persistence of invoices. Everything here runs inside the caller's transaction."""
from decimal import Decimal
from ..database.models import Invoice, InvoiceLineItem
from ..validation.financial_validator import q
from .common import audit
from .payment_service import recalc

APPROVED = {"AUTO_APPROVED_FOR_AP", "APPROVED", "PAID"}
FIN_FIELDS = ["Subtotal", "Tax_Amount", "Discount_Amount", "Other_Charges", "Total_Amount", "Currency"]

def _apply(inv: Invoice, d: dict, vendor_id, po_id, source):
    inv.Vendor_ID = vendor_id
    inv.Invoice_Number = d["invoice_number"]
    inv.Normalized_Invoice_Number = d["norm_number"]
    inv.Invoice_Date, inv.Due_Date, inv.PO_ID = d.get("invoice_date"), d.get("due_date"), po_id
    inv.Currency = d.get("currency") or "INR"
    inv.Subtotal = d.get("subtotal") or Decimal(0)
    inv.Tax_Amount = d.get("tax") or Decimal(0)
    inv.Discount_Amount = d.get("discount") or Decimal(0)
    inv.Other_Charges = d.get("other") or Decimal(0)
    inv.Total_Amount = d["total"]
    inv.Source_Type = inv.Source_Type or source

def _set_lines(inv, lines):
    inv.lines.clear()
    for l in lines:
        amt = q(l["quantity"] * l["unit_price"])
        inv.lines.append(InvoiceLineItem(Description=l["description"][:300], Item_Code=l.get("item_code"),
            Quantity=l["quantity"], Unit_Price=l["unit_price"], Tax_Rate=l.get("tax_rate") or 0,
            Tax_Amount=q(amt * (l.get("tax_rate") or 0) / 100), Line_Total=l.get("line_total") or amt))

def create_invoice(db, d, vendor_id, po_id, source, status, decision) -> Invoice:
    inv = Invoice(Source_Type=source, Total_Amount=d["total"])
    _apply(inv, d, vendor_id, po_id, source)
    inv.Invoice_Status, inv.Decision_Status = status, decision
    db.add(inv); db.flush()
    _set_lines(inv, d.get("lines", []))
    recalc(db, inv)
    audit(db, "Invoice", inv.Invoice_ID, "CREATED", new={"number": inv.Invoice_Number, "total": inv.Total_Amount, "source": source})
    return inv

def update_invoice(db, inv: Invoice, d, vendor_id, po_id, source, status, decision, reviewer_initiated: bool):
    """Returns (updated: bool, conflict_msg|None). Approved invoices are never silently overwritten."""
    new_vals = {"Subtotal": d.get("subtotal") or Decimal(0), "Tax_Amount": d.get("tax") or Decimal(0),
                "Discount_Amount": d.get("discount") or Decimal(0), "Other_Charges": d.get("other") or Decimal(0),
                "Total_Amount": d["total"], "Currency": d.get("currency") or "INR"}
    changed = {k: (getattr(inv, k), v) for k, v in new_vals.items() if getattr(inv, k) != v}
    if inv.Invoice_Status in APPROVED and changed and not reviewer_initiated:
        msg = "Approved invoice has conflicting values: " + ", ".join(f"{k}: {o} -> {n}" for k, (o, n) in changed.items())
        audit(db, "Invoice", inv.Invoice_ID, "UPDATE_CONFLICT", old={k: o for k, (o, n) in changed.items()},
              new={k: n for k, (o, n) in changed.items()}, reason="Not applied; sent to review")
        return False, msg
    # metadata that is safe to fill/refresh
    meta_changes = {}
    if reviewer_initiated:   # reviewer may correct identity fields; recorded in audit below
        for attr, nv in (("Vendor_ID", vendor_id), ("Invoice_Number", d["invoice_number"]),
                         ("Normalized_Invoice_Number", d["norm_number"])):
            if getattr(inv, attr) != nv:
                meta_changes[attr] = (getattr(inv, attr), nv)
    for attr, key in (("Invoice_Date", "invoice_date"), ("Due_Date", "due_date")):
        nv = d.get(key)
        if nv and getattr(inv, attr) != nv:
            meta_changes[attr] = (getattr(inv, attr), nv)
    if inv.PO_ID is None and po_id:
        meta_changes["PO_ID"] = (None, po_id)
    for k, (o, n) in meta_changes.items():
        setattr(inv, k, n)
    if changed:
        for k, (o, n) in changed.items():
            setattr(inv, k, n)
        _set_lines(inv, d.get("lines", [])) if d.get("lines") else None
    if changed or meta_changes:
        audit(db, "Invoice", inv.Invoice_ID, "UPDATED", old={k: o for k, (o, n) in {**changed, **meta_changes}.items()},
              new={k: n for k, (o, n) in {**changed, **meta_changes}.items()})
    if status and not (inv.Invoice_Status in APPROVED):
        inv.Invoice_Status, inv.Decision_Status = status, decision
    recalc(db, inv)
    return True, None
