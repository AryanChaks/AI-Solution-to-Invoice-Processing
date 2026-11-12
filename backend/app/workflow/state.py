from typing import Any, Dict, List, Optional, TypedDict

class InvoiceState(TypedDict, total=False):
    run_id: int
    source: str                 # MANUAL | EXCEL | PDF | IMAGE
    file_path: Optional[str]
    file_name: Optional[str]
    file_hash: Optional[str]
    skip_extraction: bool       # reprocess / manual / excel start at normalisation
    reprocess_invoice_id: Optional[int]
    doc_type: str
    inspect: dict
    words: list
    page_texts: list
    tables: list
    ocr_pages: list
    avg_ocr_conf: Optional[float]
    extraction_failed: bool
    raw: Dict[str, Any]         # string-valued fields: {"invoice":{}, "lines":[], "gstins":[], "vendor_id", "po_id", "payment"}
    evidence: Dict[str, dict]   # field -> {value, confidence, page, bbox, method, validation, corrected}
    invoice: dict               # typed values
    missing: List[str]
    low_conf: List[str]
    vendor_id: Optional[int]
    vendor_name: Optional[str]
    vendor_approved: bool
    vendor_reason: str
    dup: dict
    target_invoice_id: Optional[int]
    po: Optional[dict]
    po_ambiguous: bool
    candidates: list
    consumption: dict
    recon: dict
    findings: List[dict]
    decision: dict
    invoice_id: Optional[int]
    payment: Optional[dict]
    payment_error: Optional[str]
    error: Optional[str]
