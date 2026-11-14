"""python scripts\\check_environment.py  -> verifies everything the app needs and says what is missing."""
import os, shutil, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, ROOT); os.chdir(ROOT)
ok = lambda m: print(f"  [OK]   {m}")
bad = lambda m: print(f"  [FAIL] {m}")
warn = lambda m: print(f"  [WARN] {m}")
print(f"Python {sys.version.split()[0]}"); (ok if sys.version_info >= (3, 11) else bad)("Python 3.11+ required")
print("Python packages")
for mod in ["fastapi", "uvicorn", "sqlalchemy", "pyodbc", "pydantic", "pydantic_settings", "langgraph", "sse_starlette", "pdfplumber", "fitz", "pytesseract", "PIL", "pandas", "openpyxl", "httpx", "multipart"]:
    try: __import__(mod); ok(mod)
    except Exception as e: bad(f"{mod} ({e}) -> pip install -r backend\\requirements.txt")
print("SQL Server")
try:
    import pyodbc
    drv = [d for d in pyodbc.drivers() if "SQL Server" in d]; (ok if drv else bad)(f"ODBC drivers: {drv or 'none — install ODBC Driver 18 for SQL Server'}")
    from app.config import settings
    from sqlalchemy import create_engine, text
    try:
        with create_engine(settings.db_url).connect() as c: c.execute(text("SELECT 1")); ok(f"Connected to {settings.sql_server} / {settings.sql_database}")
    except Exception as e: bad(f"Connection failed: {str(e)[:300]}\n         (database missing? run: python scripts\\create_database.py)")
except Exception as e: bad(str(e))
print("OCR")
try:
    from app.extraction.ocr_service import tesseract_available
    import pytesseract
    if tesseract_available():
        ok("Tesseract v" + str(pytesseract.get_tesseract_version()))
    else:
        bad("Tesseract not found - install it and set TESSERACT_PATH in backend\\.env")
except Exception as e: bad(str(e))
print("Optional: Ollama")
try:
    from app.extraction.llm_extractor import llm_available
    from app.config import settings
    (ok if llm_available() else warn)(f"Model '{settings.ollama_model or '(unset)'}' " + ("available" if llm_available() else "not available — app runs without it (rules-based extraction)"))
except Exception as e: warn(str(e))
print("Frontend tooling")
for t in ("node", "npm"): (ok if shutil.which(t) else bad)(f"{t}: {shutil.which(t) or 'not found'}")
