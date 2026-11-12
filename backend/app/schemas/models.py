from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class LineIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    item_code: Optional[str] = None
    quantity: str
    unit_price: str
    tax_rate: Optional[str] = "0"
    line_total: Optional[str] = None

class PaymentIn(BaseModel):
    amount: Optional[str] = None
    date: Optional[str] = None
    method: Optional[str] = None
    ref: Optional[str] = None
    image_amount: Optional[str] = None
    source: str = "MANUAL"

class ManualInvoice(BaseModel):
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    invoice_number: str
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    po_number: Optional[str] = None
    currency: str = "INR"
    subtotal: Optional[str] = None
    tax: Optional[str] = None
    discount: Optional[str] = "0"
    other: Optional[str] = "0"
    total: Optional[str] = None
    notes: Optional[str] = None
    lines: List[LineIn] = []
    payment: Optional[PaymentIn] = None

class VendorIn(BaseModel):
    Vendor_Name: str = Field(min_length=2)
    Tax_ID: Optional[str] = None
    Vendor_Code: Optional[str] = None
    Primary_Address: Optional[str] = None
    Email: Optional[str] = None
    Contact_Number: Optional[str] = None
    Is_Approved: bool = False
    Is_Active: bool = True
    aliases: List[str] = []

class POLineIn(BaseModel):
    Item_Code: Optional[str] = None
    Description: str
    Quantity: str
    Unit_Price: str
    Tax_Rate: str = "0"

class POIn(BaseModel):
    PO_Number: str
    Vendor_ID: int
    PO_Date: str
    Currency: str = "INR"
    PO_Status: str = "OPEN"
    lines: List[POLineIn] = []

class ReasonIn(BaseModel):
    reason: str = Field(min_length=5)

class CorrectIn(BaseModel):
    corrections: Dict[str, Any] = {}
    reason: str = Field(min_length=5)

class ReprocessIn(BaseModel):
    corrections: Dict[str, Any] = {}
    reason: Optional[str] = "Reprocess"

class PaymentCreate(BaseModel):
    amount: str
    date: str
    method: Optional[str] = None
    ref: Optional[str] = None
    image_amount: Optional[str] = None

class InvoiceUpdate(BaseModel):
    Due_Date: Optional[str] = None
    reason: str = Field(min_length=5)
