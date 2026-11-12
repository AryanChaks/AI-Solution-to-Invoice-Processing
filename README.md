# InvoiceAP — AI-assisted Accounts Payable automation (local, Windows)

FastAPI + LangGraph + SQL Server Express + React/Vite/Tailwind. Everything runs on `localhost`; no cloud, no paid services.
Deterministic Python makes every financial decision; the optional local LLM (Ollama) only helps *read* documents and can never approve anything.

> **Honest status.** This code was written without access to your machine's SQL Server, Tesseract, npm registry or Ollama, so the
> full stack has **not been executed end to end**. What *was* executed: the core logic tests, the regex extractor against the generated
> sample PDFs, and Python syntax checks of every file. Expect to fix small first-run issues. Run `python scripts\check_environment.py` first,
> then `scripts\run_tests.ps1`; the tests exercise the real LangGraph workflow against SQLite and will surface most problems quickly.

## 1. What to install (Windows)

| # | Software | Purpose | Official download |
|---|----------|---------|-------------------|
| 1 | Python 3.11+ | backend | https://www.python.org/downloads/ (tick **Add python.exe to PATH**) |
| 2 | SQL Server Express | the database **engine** | https://www.microsoft.com/sql-server/sql-server-downloads → Express → *Basic* install |
| 3 | ODBC Driver 18 for SQL Server | lets Python (pyodbc) talk to SQL Server | https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server |
| 4 | SSMS (optional but handy) | GUI **client** to browse the DB — *not* the engine | https://aka.ms/ssmsfullsetup |
| 5 | Node.js LTS (includes npm) | frontend | https://nodejs.org |
| 6 | Tesseract OCR | OCR engine (separate from the `pytesseract` pip package) | https://github.com/UB-Mannheim/tesseract/wiki (default path `C:\Program Files\Tesseract-OCR`) |
| 7 | Ollama (optional) | local LLM; **no API key** | https://ollama.com/download |

Verify in a new PowerShell: `python --version`, `node --version`, `npm --version`, `& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version`, `ollama --version`.
Versions/links change — if a page has moved, search the product name on microsoft.com / the vendor site.

### SQL Server Express notes
* Basic install gives the named instance **`localhost\SQLEXPRESS`** with Windows Authentication (your Windows login is admin).
* Check the service: `Get-Service 'MSSQL$SQLEXPRESS'` → should be *Running*; start with `Start-Service 'MSSQL$SQLEXPRESS'` (admin).
* A default (unnamed) instance? set `SQL_SERVER=localhost` instead.
* The `.env` connection already adds `TrustServerCertificate=yes` (needed for Driver 18 + local self-signed certificate).

## 2. Setup

```powershell
cd InvoiceAP
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1      # venv + pip + npm install + creates backend\.env
notepad backend\.env                                           # set SQL_SERVER and TESSERACT_PATH
.\.venv\Scripts\Activate.ps1                                   # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python scripts\check_environment.py                            # tells you exactly what is missing
python scripts\create_database.py                              # creates database InvoiceAP if absent
python scripts\seed_database.py                                # creates tables + demo vendors/POs/payments
```
Reset demo data any time: `python scripts\seed_database.py --reset --yes` (drops all tables!).

**SQL authentication instead of Windows auth:** in `.env` set `SQL_TRUSTED_CONNECTION=false`, `SQL_USER`, `SQL_PASSWORD`.
**Ollama (optional):** `ollama pull qwen2.5:7b-instruct` (~5 GB download, ~8 GB RAM) then `OLLAMA_MODEL=qwen2.5:7b-instruct` in `.env`.
Smaller machines: `qwen2.5:3b-instruct` (~4 GB RAM). Without Ollama the app uses rules-based extraction and sends uncertain fields to review.

## 3. Run (two terminals)

```powershell
# Terminal 1 – backend  → http://127.0.0.1:8000  (API docs: /docs, health: /api/health)
powershell -File scripts\run_backend.ps1
# Terminal 2 – frontend → http://localhost:5173
powershell -File scripts\run_frontend.ps1
```
Tests: `powershell -File scripts\run_tests.ps1` (SQLite, never touches SQL Server). Regenerate the sample files: `python scripts\generate_sample_data.py`.

## 4. Try the scenarios (files in `sample_data/`)

Seed data: vendors Apex / Bluewave / Crestline (approved) and Dunmore (**unapproved**); POs PO-1001…PO-3002 plus a cancelled PO-4001; historical invoice BWL-7700 with two partial UPI payments.

| Scenario | Do this | Expected |
|---|---|---|
| Happy path | Add Invoice → PDF → `01_apex_INV-2026-0042_happy_path.pdf` | live timeline, **AUTO_APPROVED_FOR_AP** |
| Other layouts | upload `06_crestline_CR-5001…` (header-band layout) and `05_bluewave…` (borderless) | different layouts parsed |
| PO overrun (edge 2) | upload `02`, `03`, then `04` (₹40k, 35k, 30k vs ₹1,00,000 PO) | third → **REVIEW_REQUIRED**, PO_OVERRUN, remaining ₹25,000 |
| Price discrepancy (edge 4) | `05_bluewave_BWL-7788…` (₹1,100 vs PO ₹1,000 × 100) | ₹10,000 PRICE_VARIANCE → review |
| Poor scan (edge 1) | `07_crestline_CR-5002_poor_scan.pdf` (needs Tesseract) | OCR runs, low-confidence/missing fields → review; correct them in Review and reprocess |
| Duplicate via other channel (edge 3) | upload `06…` as PDF, then Excel tab → `vendor_bills_nonstandard_columns.csv` | row "CR 5001" → CONFIRMED_DUPLICATE, no new invoice |
| Spreadsheet mapping | Excel tab → map columns → Dry run → Import | row-level errors for bad date / missing number; unknown vendor → review |
| UPI image | Single Invoice → *Record a payment* → upload `upi_payment_utr_412345678901.png` | UTR + amount pre-filled, editable |
| Manual review | Review Queue → open item → correct → reason → Approve/Reject | stored in Audit trail |

## 5. Architecture (short)
`backend/app/workflow` LangGraph graph (nodes are thin; each logs a persisted `Processing_Events` row, which the SSE endpoint streams) ·
`validation/` Decimal reconciliation, tolerance, rule engine · `matching/` PO matching + consumption + duplicate classification ·
`extraction/` pdfplumber / PyMuPDF / Tesseract / regex / optional Ollama (output schema-validated **and grounded in the document text**, else discarded) ·
`services/` persistence (idempotent; approved invoices never silently overwritten; PO capacity re-checked under an UPDLOCK inside the commit transaction).
Branches: extraction failed → decision; critical field missing → decision; confirmed duplicate → decision (skips PO/recon); any exception → FAILED (technical, distinct from business outcomes).

## 6. Deliberate deviations / limitations (please read)
* **shadcn/ui**: its CLI needs network/interactive setup, so the UI uses hand-written Tailwind components in `frontend/src/ui.tsx` styled the same way. You can add shadcn later.
* **Alembic**: tables are created via SQLAlchemy `create_all` (idempotent). `python scripts\export_schema.py` writes `database/schema.sql`. Add Alembic when you start changing the schema.
* Review endpoints are keyed by **run id** (`/api/reviews/{run_id}/…`) rather than invoice id, because an unresolved invoice has no id yet.
* Header-only imports (Excel) skip line-level/price checks (WARNING, not error). PDFs/manual entries without lines are flagged as errors.
* Regex extraction is label-driven and tuned to common Indian GST invoice wording; unusual layouts rely on the LLM or manual correction. It never fabricates: unreadable values become missing → review.
* Money is stored as `Numeric(18,2)`; JSON responses show numbers as floats for display only — all arithmetic is `Decimal`.
* Single-user local app: no login; actor is recorded as `local-user`.
* Not covered yet: credit notes/adjustments tables, multi-currency conversion, multi-page line-item stitching, authentication.
