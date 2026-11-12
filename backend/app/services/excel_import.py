"""Spreadsheet import: column discovery, mapping suggestion, row validation (dry-run) and row-by-row processing."""
import io, re
from decimal import Decimal
import pandas as pd
from ..extraction.normalizer import parse_amount, parse_date, normalize_invoice_number
from ..services.vendor_service import resolve_vendor
from ..matching.duplicate_detector import ExistingInvoice, classify
from ..database.models import Invoice

INTERNAL = [  # (key, label, required)
    ("invoice_number", "Invoice Number", True), ("vendor_name", "Vendor Name", True), ("invoice_date", "Invoice Date", True),
    ("due_date", "Due Date", False), ("po_number", "PO Number", False), ("currency", "Currency", False),
    ("subtotal", "Subtotal", False), ("tax", "Tax Amount", False), ("discount", "Discount", False),
    ("other", "Other Charges", False), ("total", "Total Amount", True),
    ("pay_amount", "Payment Amount", False), ("pay_date", "Payment Date", False),
    ("pay_ref", "Payment Reference / UTR", False), ("pay_method", "Payment Method", False)]
SYN = {"invoice_number": ["invoice", "inv no", "bill no", "invno", "document no"], "vendor_name": ["vendor", "supplier", "party", "seller"],
       "invoice_date": ["invoice date", "inv date", "bill date", "date"], "due_date": ["due"], "po_number": ["po", "purchase order"],
       "currency": ["currency", "curr"], "subtotal": ["subtotal", "taxable", "net amount", "base"], "tax": ["tax", "gst"],
       "discount": ["discount"], "other": ["other", "freight", "shipping"], "total": ["total", "gross", "grand", "payable", "invoice amount"],
       "pay_amount": ["paid amount", "payment amount", "amount paid"], "pay_date": ["payment date", "paid on"],
       "pay_ref": ["utr", "payment ref", "transaction"], "pay_method": ["payment method", "mode"]}

class ImportError_(ValueError):
    pass

def read_table(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding_errors="replace")
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
        else:
            raise ImportError_("Unsupported spreadsheet type (use .xlsx, .xls or .csv)")
    except ImportError_:
        raise
    except Exception as e:
        raise ImportError_(f"Could not read file: {e}")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
    if df.empty:
        raise ImportError_("The file contains no data rows")
    if len(df) > 2000:
        raise ImportError_("Too many rows (limit 2000 per import)")
    return df

def suggest_mapping(columns):
    out = {}
    for key, _, _ in INTERNAL:
        best = None
        for c in columns:
            lc = c.lower()
            if lc.replace(" ", "").replace("_", "") == key.replace("_", ""):
                best = c; break
            if any(s in lc for s in SYN[key]) and c not in out.values():
                best = best or c
        if best: out[key] = best
    return out

def validate_mapping(mapping: dict, columns: list):
    errs = [f"'{lbl}' is required but not mapped" for k, lbl, req in INTERNAL if req and not mapping.get(k)]
    errs += [f"Mapped column '{v}' does not exist in file" for v in mapping.values() if v and v not in columns]
    used = [v for v in mapping.values() if v]
    if len(used) != len(set(used)):
        errs.append("The same file column is mapped to more than one field")
    return errs

def row_to_raw(row: pd.Series, mapping: dict) -> tuple:
    """Returns (raw_invoice, payment_raw|None, errors)."""
    g = lambda k: (str(row[mapping[k]]).strip() if mapping.get(k) else "")
    errs = []
    inv = {k: g(k) or None for k, _, _ in INTERNAL if not k.startswith("pay_")}
    for k in ("invoice_number", "vendor_name", "invoice_date", "total"):
        if not inv.get(k): errs.append(f"{k} is empty")
    for k in ("invoice_date", "due_date"):
        if inv.get(k) and parse_date(inv[k]) is None: errs.append(f"{k} '{inv[k]}' is not a valid date")
    for k in ("subtotal", "tax", "discount", "other", "total"):
        if inv.get(k) and parse_amount(inv[k]) is None: errs.append(f"{k} '{inv[k]}' is not a valid amount")
    if inv.get("total") and (parse_amount(inv["total"]) or 0) < 0: errs.append("total is negative")
    pay = None
    pv = {k: g(k) for k in ("pay_amount", "pay_date", "pay_ref", "pay_method")}
    if any(pv[k] for k in ("pay_amount", "pay_date", "pay_ref")):
        if not (pv["pay_amount"] and pv["pay_date"] and pv["pay_ref"]):
            errs.append("incomplete payment data (amount, date and reference are all required)")
        elif parse_amount(pv["pay_amount"]) is None or parse_date(pv["pay_date"]) is None:
            errs.append("payment amount/date invalid")
        else:
            pay = {"amount": pv["pay_amount"], "date": pv["pay_date"], "ref": pv["pay_ref"], "method": pv["pay_method"] or "UPI", "source": "EXCEL"}
    return inv, pay, errs

def preview_duplicate(db, inv: dict) -> dict:
    v, why = resolve_vendor(db, name=inv.get("vendor_name"))
    if not v: return {"vendor": None, "dup": "VENDOR_UNKNOWN"}
    norm = normalize_invoice_number(inv.get("invoice_number"))
    ex = [ExistingInvoice(i.Invoice_ID, i.Vendor_ID, i.Normalized_Invoice_Number, i.Invoice_Date, i.Total_Amount, [])
          for i in db.query(Invoice).filter(Invoice.Vendor_ID == v.Vendor_ID)]
    d = classify(v.Vendor_ID, norm, parse_date(inv.get("invoice_date")), parse_amount(inv.get("total")), None, ex)
    return {"vendor": v.Vendor_Name, "dup": d.outcome, "existing_invoice_id": d.invoice_id}
