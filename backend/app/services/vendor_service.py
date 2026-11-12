import re
from ..database.models import Vendor, VendorAlias
from ..extraction.normalizer import normalize_vendor_name

def resolve_vendor(db, name=None, gstin=None, vendor_id=None):
    """Priority: explicit id > registered GSTIN > exact normalised name/alias. NEVER fuzzy-only."""
    if vendor_id:
        v = db.get(Vendor, int(vendor_id))
        return (v, "Selected explicitly") if v else (None, f"Vendor id {vendor_id} not found")
    if gstin:
        g = re.sub(r"\s", "", gstin).upper()
        v = db.query(Vendor).filter(Vendor.Tax_ID == g).first()
        if v: return v, f"Matched by registered GSTIN {g}"
    if name:
        n = normalize_vendor_name(name)
        if n:
            vs = db.query(Vendor).filter(Vendor.Normalized_Vendor_Name == n).all()
            if len(vs) == 1: return vs[0], "Matched by exact normalised name"
            if len(vs) > 1: return None, "Multiple vendors share this name; GSTIN needed"
            al = db.query(VendorAlias).filter(VendorAlias.Normalized_Alias == n).all()
            if len(al) == 1: return al[0].vendor, "Matched by registered alias"
    return None, "No registered vendor matched"

def vendor_known_in_text(db, text: str):
    """Look for any registered GSTIN or exact vendor name inside document text."""
    up = text.upper()
    for v in db.query(Vendor).all():
        if v.Tax_ID and v.Tax_ID.upper() in up:
            return v
    low = " ".join(text.lower().split())
    for v in db.query(Vendor).all():
        if v.Vendor_Name and " ".join(v.Vendor_Name.lower().split()) in low:
            return v
        for a in v.aliases:
            if " ".join(a.Alias.lower().split()) in low:
                return v
    return None
