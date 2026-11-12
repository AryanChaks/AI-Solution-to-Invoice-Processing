from decimal import Decimal
from ..database.models import Payment, Invoice
from ..extraction.normalizer import normalize_utr
from .common import audit

class PaymentError(ValueError):
    pass

def recalc(db, inv: Invoice):
    """Outstanding = Total - sum(completed payments). Payments are the source of truth."""
    db.flush()
    paid = sum((p.Payment_Amount for p in db.query(Payment).filter_by(Invoice_ID=inv.Invoice_ID, Payment_Status="COMPLETED")), Decimal(0))
    inv.Total_Paid = paid
    inv.Outstanding_Amount = inv.Total_Amount - paid
    if inv.Outstanding_Amount <= 0 and inv.Total_Amount > 0 and inv.Invoice_Status in ("AUTO_APPROVED_FOR_AP", "APPROVED", "PAID"):
        inv.Invoice_Status = "PAID"

def add_payment(db, inv: Invoice, amount: Decimal, pay_date, method, ref, source="MANUAL", image_amount=None, actor="local-user") -> Payment:
    if amount is None or amount <= 0:
        raise PaymentError("Payment amount must be positive.")
    if pay_date is None:
        raise PaymentError("Payment date is required.")
    norm = normalize_utr(ref) or None
    if norm:
        dup = db.query(Payment).filter_by(Normalized_Ref_Number=norm).first()
        if dup:
            raise PaymentError(f"Reference {ref} already recorded on payment #{dup.Payment_ID} (invoice #{dup.Invoice_ID}).")
    outstanding = inv.Total_Amount - (inv.Total_Paid or 0)
    if amount > outstanding:
        raise PaymentError(f"Payment {amount} exceeds outstanding {outstanding}.")
    p = Payment(Invoice_ID=inv.Invoice_ID, Payment_Date=pay_date, Payment_Amount=amount, Payment_Method=method,
                Ref_Number=ref, Normalized_Ref_Number=norm, Source_Type=source, Amount_Extracted_From_Image=image_amount)
    db.add(p)
    recalc(db, inv)
    audit(db, "Payment", inv.Invoice_ID, "PAYMENT_ADDED", new={"amount": amount, "ref": ref}, actor=actor)
    return p
