"""Deterministic, label-driven field extraction + evidence grounding (page/bbox/confidence)."""
import re
from decimal import Decimal
from typing import Optional
from .normalizer import parse_amount, parse_date

DATE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{4})"
AMT_DEC = re.compile(r"(?<![\w.])(\d[\d,]*\.\d{1,2})(?![\d])")
AMT_INT = re.compile(r"(?<![\w.])(\d[\d,]{2,})(?![\d.])")
GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")

def _norm_tok(s: str) -> str:
    return re.sub(r"[^\w.]", "", s).lower()

def locate(words: list, value: str):
    """Find the word run matching `value`. Returns (page, bbox, mean_ocr_conf|None) or None."""
    toks = [_norm_tok(t) for t in str(value).split() if _norm_tok(t)]
    if not toks:
        return None
    nw = [_norm_tok(w["text"]) for w in words]
    for i in range(len(words) - len(toks) + 1):
        if nw[i:i + len(toks)] == toks and all(words[i + k]["page"] == words[i]["page"] for k in range(len(toks))):
            seg = words[i:i + len(toks)]
            confs = [w["conf"] for w in seg if w["conf"] is not None]
            return (seg[0]["page"], (min(w["x0"] for w in seg), min(w["y0"] for w in seg),
                                     max(w["x1"] for w in seg), max(w["y1"] for w in seg)),
                    sum(confs) / len(confs) if confs else None)
    return None

def _last_amount(line: str) -> Optional[str]:
    m = AMT_DEC.findall(line) or AMT_INT.findall(line)
    return m[-1] if m else None

def _amount_by_labels(lines, labels, exclude=None):
    for lab in labels:  # priority order
        hits = [l for l in lines if re.search(lab, l, re.I) and not (exclude and re.search(exclude, l, re.I))]
        for l in reversed(hits):
            a = _last_amount(l)
            if a and parse_amount(a) is not None:
                return a
    return None

def _ref(text, patterns):
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip(" :.-")
    return None

def extract_fields(page_texts, words, tables, ocr_pages, avg_ocr_conf):
    text = "\n".join(page_texts)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    raw = {}
    raw["invoice_number"] = _ref(text, [r"(?:tax\s+)?invoice\s*(?:no|number|#|num)\.?\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/\-_.]{1,30})",
                                        r"\binv(?:oice)?\s*(?:no|#)\.?\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/\-_.]{1,30})",
                                        r"bill\s*(?:no|number)\.?\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/\-_.]{1,30})"])
    raw["invoice_date"] = _ref(text, [r"invoice\s*date\s*[:\-]?\s*" + DATE, r"\bdate\s*of\s*issue\s*[:\-]?\s*" + DATE,
                                      r"(?<!due )(?<!due)\bdate\s*[:\-]\s*" + DATE])
    raw["due_date"] = _ref(text, [r"due\s*date\s*[:\-]?\s*" + DATE, r"payment\s*due\s*[:\-]?\s*" + DATE])
    raw["po_number"] = _ref(text, [r"(?:purchase\s*order|\bp\.?o\.?(?=[\s:#.]))\s*(?:no|number|ref(?:erence)?|#)?\.?\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/\-_.]{2,30})"])
    if raw["po_number"] and raw["po_number"].lower() in ("date", "number", "no", "ref"):
        raw["po_number"] = None
    gst = GSTIN.findall(text.upper())
    raw["gstin_candidates"] = list(dict.fromkeys(gst))
    raw["total"] = _amount_by_labels(lines, [r"grand\s*total", r"total\s*amount\s*(payable|due)?", r"amount\s*due", r"net\s*payable",
                                             r"invoice\s*total", r"^total\b"], exclude=r"sub\s*-?total|taxable|total\s*tax|in\s*words")
    raw["subtotal"] = _amount_by_labels(lines, [r"sub\s*-?\s*total", r"taxable\s*(value|amount)", r"total\s*before\s*tax"])
    taxes = [_last_amount(l) for l in lines if re.search(r"^\s*(cgst|sgst|utgst|igst)\b", l, re.I) and _last_amount(l)]
    if not taxes:
        t = _amount_by_labels(lines, [r"^\s*(gst|vat|tax)\b[^a-z]"], exclude=r"invoice|taxable|gstin|id")
        taxes = [t] if t else []
    raw["tax"] = str(sum((parse_amount(t) or Decimal(0) for t in taxes), Decimal(0))) if taxes else None
    raw["discount"] = _amount_by_labels(lines, [r"discount"])
    raw["other"] = _amount_by_labels(lines, [r"freight|shipping|handling|packing|other\s*charges"])
    cur = None
    if re.search(r"₹|\bINR\b|\bRs\.?\b", text): cur = "INR"
    elif re.search(r"\bUSD\b|\$", text): cur = "USD"
    elif re.search(r"\bEUR\b|€", text): cur = "EUR"
    raw["currency"] = cur

    fields, ocr_set = {}, {p + 1 for p in ocr_pages}
    for name, val in raw.items():
        if name == "gstin_candidates" or val in (None, ""):
            continue
        val = str(val)
        loc = locate(words, val)
        page, bbox, wconf = (loc if loc else (None, None, None))
        valid = True
        if name in ("invoice_date", "due_date"): valid = parse_date(val) is not None
        if name in ("total", "subtotal", "tax", "discount", "other"): valid = parse_amount(val) is not None
        if page in ocr_set or (page is None and ocr_set):
            base = wconf if wconf is not None else (avg_ocr_conf or 0.4) * 0.8   # grounded in OCR confidence
        else:
            base = 0.95 if loc else 0.8
        conf = round(base * (1.0 if valid else 0.3), 3)
        fields[name] = {"value": val, "confidence": conf, "page": page, "bbox": bbox,
                        "method": "OCR_REGEX" if (page in ocr_set or (page is None and ocr_set)) else "TEXT_REGEX",
                        "validation": "VALID" if valid else "INVALID"}
    if cur and "currency" in fields and not re.search(r"₹|\bINR\b|\bUSD\b|\$|€|\bEUR\b|\bRs", text):
        fields["currency"]["method"] = "INFERRED_DEFAULT"
    return {"fields": fields, "gstins": raw["gstin_candidates"],
            "lines": extract_lines(lines, tables, words, ocr_set, avg_ocr_conf)}

_HDR = [("code", r"item\s*code|sku|part|^code"), ("desc", r"desc|item|particular|product|service"), ("qty", r"qty|quantity|nos"),
        ("price", r"unit\s*price|rate|price"), ("tax", r"tax|gst|vat"), ("total", r"amount|total")]

def _table_lines(tables):
    out = []
    for pg in tables:
        for t in pg:
            if not t or len(t) < 2: continue
            hdr = [(c or "").strip().lower() for c in t[0]]
            idx = {}
            for j, h in enumerate(hdr):          # classify each header cell once, first matching role wins
                for key, pat in _HDR:
                    if re.search(pat, h):
                        idx.setdefault(key, j); break
            if not {"desc", "qty", "price"} <= idx.keys(): continue
            for row in t[1:]:
                g = lambda k: (row[idx[k]] or "").strip() if k in idx and idx[k] < len(row) and row[idx[k]] else ""
                q, p = parse_amount(g("qty")), parse_amount(g("price"))
                if not g("desc") or q is None or p is None or re.search(r"total", g("desc"), re.I): continue
                tx = parse_amount(g("tax").replace("%", "")) if g("tax") else Decimal(0)
                out.append({"description": g("desc").replace("\n", " "), "item_code": g("code") or None,
                            "quantity": str(q), "unit_price": str(p), "tax_rate": str(tx or 0),
                            "line_total": str(parse_amount(g("total"))) if parse_amount(g("total")) is not None else None,
                            "method": "TABLE"})
    return out

_LINE = re.compile(r"^(?:\d{1,2}[.)]?\s+(?=[A-Za-z]))?(?:(?P<code>[A-Z][A-Z0-9]+-[A-Z0-9-]+)\s+)?(?P<desc>[A-Za-z].+?)\s+"
                   r"(?P<qty>\d+(?:\.\d+)?)\s+(?:[A-Za-z]{2,4}\s+)?(?P<price>[\d,]+\.\d{2})\s+(?:(?P<tax>\d+(?:\.\d+)?)%\s+)?(?P<total>[\d,]+\.\d{2})$")

def extract_lines(lines, tables, words, ocr_set, avg_conf):
    tl = _table_lines(tables)
    if tl:
        return tl
    out = []
    for l in lines:
        m = _LINE.match(l)
        if m and not re.search(r"total|tax|gst", m.group("desc"), re.I):
            out.append({"description": m.group("desc").strip(), "item_code": m.group("code"), "quantity": m.group("qty"),
                        "unit_price": m.group("price").replace(",", ""), "tax_rate": m.group("tax") or "0",
                        "line_total": m.group("total").replace(",", ""), "method": "TEXT_REGEX"})
    return out
