"""SQLAlchemy 2.0 models. Money = Numeric(18,2); rates Numeric(7,4); never float."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (ForeignKey, Numeric, String, Text, Date, DateTime, Boolean, Integer,
                        UniqueConstraint, Index, CheckConstraint, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONEY = Numeric(18, 2)

class Base(DeclarativeBase):
    pass

class Vendor(Base):
    __tablename__ = "Vendors"
    Vendor_ID: Mapped[int] = mapped_column(primary_key=True)
    Vendor_Name: Mapped[str] = mapped_column(String(200))
    Normalized_Vendor_Name: Mapped[str] = mapped_column(String(200), index=True)
    Tax_ID: Mapped[Optional[str]] = mapped_column(String(30))   # GSTIN
    Vendor_Code: Mapped[Optional[str]] = mapped_column(String(30))
    Primary_Address: Mapped[Optional[str]] = mapped_column(String(500))
    Email: Mapped[Optional[str]] = mapped_column(String(200))
    Contact_Number: Mapped[Optional[str]] = mapped_column(String(30))
    Is_Approved: Mapped[bool] = mapped_column(Boolean, default=False)
    Is_Active: Mapped[bool] = mapped_column(Boolean, default=True)
    Created_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    Updated_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    aliases: Mapped[list["VendorAlias"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")

class VendorAlias(Base):
    __tablename__ = "Vendor_Aliases"
    Alias_ID: Mapped[int] = mapped_column(primary_key=True)
    Vendor_ID: Mapped[int] = mapped_column(ForeignKey("Vendors.Vendor_ID"))
    Alias: Mapped[str] = mapped_column(String(200))
    Normalized_Alias: Mapped[str] = mapped_column(String(200), index=True)
    vendor: Mapped[Vendor] = relationship(back_populates="aliases")

class PurchaseOrder(Base):
    __tablename__ = "PurchaseOrders"
    PO_ID: Mapped[int] = mapped_column(primary_key=True)
    PO_Number: Mapped[str] = mapped_column(String(50), unique=True)
    Vendor_ID: Mapped[int] = mapped_column(ForeignKey("Vendors.Vendor_ID"))
    PO_Date: Mapped[date] = mapped_column(Date)
    Currency: Mapped[str] = mapped_column(String(3), default="INR")
    PO_Total_Amount: Mapped[Decimal] = mapped_column(MONEY)
    PO_Status: Mapped[str] = mapped_column(String(20), default="OPEN")
    Created_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    Updated_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    lines: Mapped[list["POLineItem"]] = relationship(back_populates="po", cascade="all, delete-orphan")

class POLineItem(Base):
    __tablename__ = "PurchaseOrder_Line_Items"
    PO_Line_ID: Mapped[int] = mapped_column(primary_key=True)
    PO_ID: Mapped[int] = mapped_column(ForeignKey("PurchaseOrders.PO_ID"))
    Item_Code: Mapped[Optional[str]] = mapped_column(String(50))
    Description: Mapped[str] = mapped_column(String(300))
    Quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    Unit_Price: Mapped[Decimal] = mapped_column(MONEY)
    Tax_Rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    Line_Total: Mapped[Decimal] = mapped_column(MONEY)
    po: Mapped[PurchaseOrder] = relationship(back_populates="lines")

class Invoice(Base):
    __tablename__ = "Invoices"
    __table_args__ = (
        UniqueConstraint("Vendor_ID", "Normalized_Invoice_Number", name="UQ_Invoice_Vendor_Number"),
        CheckConstraint("Total_Amount >= 0", name="CK_Invoice_Total_NonNeg"),
    )
    Invoice_ID: Mapped[int] = mapped_column(primary_key=True)
    Vendor_ID: Mapped[int] = mapped_column(ForeignKey("Vendors.Vendor_ID"))
    Invoice_Number: Mapped[str] = mapped_column(String(60))
    Normalized_Invoice_Number: Mapped[str] = mapped_column(String(60))
    Invoice_Date: Mapped[Optional[date]] = mapped_column(Date)
    Due_Date: Mapped[Optional[date]] = mapped_column(Date)
    PO_ID: Mapped[Optional[int]] = mapped_column(ForeignKey("PurchaseOrders.PO_ID"), index=True)
    Currency: Mapped[str] = mapped_column(String(3), default="INR")
    Subtotal: Mapped[Decimal] = mapped_column(MONEY, default=0)
    Tax_Amount: Mapped[Decimal] = mapped_column(MONEY, default=0)
    Discount_Amount: Mapped[Decimal] = mapped_column(MONEY, default=0)
    Other_Charges: Mapped[Decimal] = mapped_column(MONEY, default=0)
    Total_Amount: Mapped[Decimal] = mapped_column(MONEY)
    Total_Paid: Mapped[Decimal] = mapped_column(MONEY, default=0)       # derived from Payments
    Outstanding_Amount: Mapped[Decimal] = mapped_column(MONEY, default=0)  # derived
    Invoice_Status: Mapped[str] = mapped_column(String(30), default="RECEIVED")
    Decision_Status: Mapped[Optional[str]] = mapped_column(String(30))
    Source_Type: Mapped[str] = mapped_column(String(20))  # MANUAL | EXCEL | PDF
    Created_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    Updated_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    lines: Mapped[list["InvoiceLineItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")

class InvoiceLineItem(Base):
    __tablename__ = "Invoice_Line_Items"
    Line_Item_ID: Mapped[int] = mapped_column(primary_key=True)
    Invoice_ID: Mapped[int] = mapped_column(ForeignKey("Invoices.Invoice_ID"), index=True)
    Description: Mapped[str] = mapped_column(String(300))
    Item_Code: Mapped[Optional[str]] = mapped_column(String(50))
    Quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    Unit_Price: Mapped[Decimal] = mapped_column(MONEY)
    Tax_Rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    Tax_Amount: Mapped[Decimal] = mapped_column(MONEY, default=0)
    Line_Total: Mapped[Decimal] = mapped_column(MONEY)
    invoice: Mapped[Invoice] = relationship(back_populates="lines")

class Payment(Base):
    __tablename__ = "Payments"
    Payment_ID: Mapped[int] = mapped_column(primary_key=True)
    Invoice_ID: Mapped[int] = mapped_column(ForeignKey("Invoices.Invoice_ID"), index=True)
    Payment_Date: Mapped[date] = mapped_column(Date)
    Payment_Amount: Mapped[Decimal] = mapped_column(MONEY)
    Payment_Method: Mapped[Optional[str]] = mapped_column(String(30))
    Ref_Number: Mapped[Optional[str]] = mapped_column(String(40))           # as entered/extracted
    Normalized_Ref_Number: Mapped[Optional[str]] = mapped_column(String(40))
    Payment_Status: Mapped[str] = mapped_column(String(20), default="COMPLETED")
    Source_Type: Mapped[str] = mapped_column(String(20), default="MANUAL")
    Amount_Extracted_From_Image: Mapped[Optional[Decimal]] = mapped_column(MONEY)  # OCR value kept for traceability
    Created_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    invoice: Mapped[Invoice] = relationship(back_populates="payments")
    # NOTE: unique-when-not-null. On SQL Server this is a FILTERED unique index (see database/schema.sql).
    __table_args__ = (
        Index("UX_Payment_Ref", "Normalized_Ref_Number", unique=True,
              mssql_where=(Normalized_Ref_Number.isnot(None)),
              sqlite_where=(Normalized_Ref_Number.isnot(None))),
        CheckConstraint("Payment_Amount > 0", name="CK_Payment_Positive"),
    )

class ProcessingRun(Base):
    __tablename__ = "Processing_Runs"
    Run_ID: Mapped[int] = mapped_column(primary_key=True)
    Invoice_ID: Mapped[Optional[int]] = mapped_column(ForeignKey("Invoices.Invoice_ID"), index=True)
    Source_Type: Mapped[str] = mapped_column(String(20))
    Uploaded_File_Name: Mapped[Optional[str]] = mapped_column(String(260))
    Stored_File_Path: Mapped[Optional[str]] = mapped_column(String(500))
    File_Hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    Processing_Status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    Started_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    Completed_At: Mapped[Optional[datetime]] = mapped_column(DateTime)
    Processing_Duration: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    Final_Decision: Mapped[Optional[str]] = mapped_column(String(30))
    Decision_Json: Mapped[Optional[str]] = mapped_column(Text)
    Parsed_Json: Mapped[Optional[str]] = mapped_column(Text)      # raw (string) fields + lines, used for reprocess
    Review_Status: Mapped[Optional[str]] = mapped_column(String(20))  # PENDING|APPROVED|REJECTED|CLARIFICATION|SUPERSEDED
    Parent_Run_ID: Mapped[Optional[int]] = mapped_column(Integer)
    Doc_Type: Mapped[Optional[str]] = mapped_column(String(20))

class ProcessingEvent(Base):
    __tablename__ = "Processing_Events"
    Event_ID: Mapped[int] = mapped_column(primary_key=True)
    Run_ID: Mapped[int] = mapped_column(ForeignKey("Processing_Runs.Run_ID"), index=True)
    Stage_Name: Mapped[str] = mapped_column(String(60))
    Stage_Status: Mapped[str] = mapped_column(String(20))
    Started_At: Mapped[Optional[datetime]] = mapped_column(DateTime)
    Completed_At: Mapped[Optional[datetime]] = mapped_column(DateTime)
    Duration: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    Input_Summary: Mapped[Optional[str]] = mapped_column(Text)
    Output_Summary: Mapped[Optional[str]] = mapped_column(Text)
    Error_Message: Mapped[Optional[str]] = mapped_column(Text)

class ExtractionEvidence(Base):
    __tablename__ = "Extraction_Evidence"
    Evidence_ID: Mapped[int] = mapped_column(primary_key=True)
    Run_ID: Mapped[int] = mapped_column(ForeignKey("Processing_Runs.Run_ID"), index=True)
    Field_Name: Mapped[str] = mapped_column(String(60))
    Extracted_Value: Mapped[Optional[str]] = mapped_column(Text)
    Corrected_Value: Mapped[Optional[str]] = mapped_column(Text)
    Confidence_Score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    Source_Page: Mapped[Optional[int]] = mapped_column(Integer)
    Bounding_Box: Mapped[Optional[str]] = mapped_column(String(100))  # "x0,y0,x1,y1"
    Extraction_Method: Mapped[Optional[str]] = mapped_column(String(30))
    Validation_Status: Mapped[Optional[str]] = mapped_column(String(20))
    Is_Manually_Corrected: Mapped[bool] = mapped_column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "Audit_Logs"
    Audit_ID: Mapped[int] = mapped_column(primary_key=True)
    Entity_Type: Mapped[str] = mapped_column(String(40))
    Entity_ID: Mapped[int] = mapped_column(Integer)
    Action: Mapped[str] = mapped_column(String(40))
    Old_Value: Mapped[Optional[str]] = mapped_column(Text)
    New_Value: Mapped[Optional[str]] = mapped_column(Text)
    Reason: Mapped[Optional[str]] = mapped_column(Text)
    Actor: Mapped[str] = mapped_column(String(80), default="system")
    Created_At: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (Index("IX_Audit_Entity", "Entity_Type", "Entity_ID"),)

class ToleranceSetting(Base):
    __tablename__ = "Tolerance_Settings"
    Key: Mapped[str] = mapped_column(String(50), primary_key=True)
    Value: Mapped[str] = mapped_column(String(50))

class ColumnMappingTemplate(Base):
    __tablename__ = "Column_Mapping_Templates"
    Template_ID: Mapped[int] = mapped_column(primary_key=True)
    Name: Mapped[str] = mapped_column(String(100), unique=True)
    Mapping_Json: Mapped[str] = mapped_column(Text)
