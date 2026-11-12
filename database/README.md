Tables are created automatically (SQLAlchemy `create_all`) on backend start or by `python scripts\seed_database.py`.
To inspect the exact T-SQL: `python scripts\export_schema.py` writes `database/schema.sql`.
Key constraints: UQ_Invoice_Vendor_Number (Vendor_ID + Normalized_Invoice_Number), filtered unique index UX_Payment_Ref on Normalized_Ref_Number, FK on every child table.
