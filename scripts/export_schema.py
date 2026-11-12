"""Writes database/schema.sql (T-SQL DDL generated from the SQLAlchemy models)."""
import os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "backend")); os.chdir(os.path.join(ROOT, "backend"))
os.environ["DATABASE_URL"] = "sqlite://"
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mssql
from app.database.models import Base
out = ["-- Generated from SQLAlchemy models. The app creates these automatically on startup; use this for review/manual setup.", "USE [InvoiceAP];", "GO"]
for t in Base.metadata.sorted_tables:
    out.append(str(CreateTable(t).compile(dialect=mssql.dialect())).strip() + ";\nGO")
    for ix in t.indexes:
        out.append(str(CreateIndex(ix).compile(dialect=mssql.dialect())).strip() + ";\nGO")
open(os.path.join(ROOT, "database", "schema.sql"), "w", encoding="utf-8").write("\n\n".join(out))
print("database/schema.sql written")
