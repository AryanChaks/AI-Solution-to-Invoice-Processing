import logging, os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .config import settings
from .database.connection import engine
from .database.models import Base
from .api import invoices, vendors, purchase_orders, processing, reviews, dashboard, settings as settings_api
from .extraction.ocr_service import tesseract_available
from .extraction.llm_extractor import llm_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("invoiceap")

app = FastAPI(title="InvoiceAP", version="1.0.0", description="AI-assisted Accounts Payable automation")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url, "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    try:
        Base.metadata.create_all(engine)   # idempotent; Alembic can be layered on later (see README)
    except Exception:
        log.exception("Database initialisation failed — check SQL_SERVER / driver / permissions in backend/.env")

@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {type(exc).__name__}: {exc}"})

for r in (invoices.router, vendors.router, purchase_orders.router, processing.router, reviews.router, dashboard.router, settings_api.router):
    app.include_router(r)

@app.get("/api/health", tags=["health"])
def health():
    db_ok, db_err = True, None
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:
        db_ok, db_err = False, str(e)[:300]
    return {"status": "ok" if db_ok else "degraded", "database": {"ok": db_ok, "error": db_err},
            "ocr": {"ok": tesseract_available()},
            "llm": {"ok": llm_available(), "model": settings.ollama_model or None, "note": "optional"}}
