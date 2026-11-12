"""Creates the InvoiceAP database on SQL Server if it does not exist (reads backend/.env). Tables are created by seed_database.py."""
import os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, ROOT); os.chdir(ROOT)
import pyodbc
from app.config import settings

auth = "Trusted_Connection=yes" if settings.sql_trusted_connection else f"UID={settings.sql_user};PWD={settings.sql_password}"
cs = f"DRIVER={{{settings.sql_driver}}};SERVER={settings.sql_server};DATABASE=master;{auth};TrustServerCertificate=yes;Encrypt=yes"
try:
    cn = pyodbc.connect(cs, autocommit=True)
except Exception as e:
    sys.exit(f"Cannot connect to SQL Server: {e}\nCheck SQL_SERVER / SQL_DRIVER in backend\\.env and that the SQL Server service is running.")
db = settings.sql_database.replace("]", "")
cn.execute(f"IF DB_ID(N'{db}') IS NULL CREATE DATABASE [{db}]")
print(f"Database [{db}] is ready on {settings.sql_server}.")
