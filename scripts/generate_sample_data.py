"""Generates synthetic (fictional) invoices as REAL PDFs, a degraded scanned PDF, a UPI screenshot and spreadsheets.
Run:  python scripts/generate_sample_data.py   (needs reportlab, Pillow, pandas, openpyxl)"""
import os, random
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sample_data")
INV, SHEET, PAY, PO = (os.path.join(ROOT, d) for d in ("invoices", "spreadsheets", "payment_images", "purchase_orders"))
for d in (INV, SHEET, PAY, PO): os.makedirs(d, exist_ok=True)
fm = lambda x: f"{x:,.2f}"

VENDORS = {
 "apex": ("Apex Industrial Supplies Pvt Ltd", "27AAAPA1234A1Z5", "Plot 14, MIDC Andheri, Mumbai 400093"),
 "blue": ("Bluewave Logistics Pvt Ltd", "29BBBCB5678B1Z3", "88 Residency Road, Bengaluru 560025"),
 "crest": ("Crestline Office Solutions Pvt Ltd", "07CCCDC9012C1Z1", "B-12 Nehru Place, New Delhi 110019"),
}
BUYER = ("Orion Manufacturing Co Pvt Ltd", "19AAAAO9999O1Z7")

def compute(lines, rate_in_lines=True):
    sub = sum(q * p for _, _, q, p, _ in lines)
    tax = sum(q * p * r / 100 for _, _, q, p, r in lines)
    return sub, tax, sub + tax

def layout_a(fn, v, inv_no, date, due, po, lines):
    """Bordered table, CGST/SGST split, dd/mm/yyyy dates."""
    c = canvas.Canvas(os.path.join(INV, fn), pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 18); c.drawString(40, H - 50, v[0])
    c.setFont("Helvetica", 9); c.drawString(40, H - 65, v[2]); c.drawString(40, H - 77, f"GSTIN: {v[1]}")
    c.setFont("Helvetica-Bold", 14); c.drawString(40, H - 110, "TAX INVOICE")
    c.setFont("Helvetica", 10)
    for i, t in enumerate([f"Invoice No: {inv_no}", f"Invoice Date: {date}", f"Due Date: {due}", f"PO Number: {po}",
                           f"Bill To: {BUYER[0]}", f"Buyer GSTIN: {BUYER[1]}"]):
        c.drawString(40, H - 135 - i * 14, t)
    rows = [["#", "Item Code", "Description", "Qty", "Rate", "GST %", "Amount"]]
    for i, (code, d, q, p, r) in enumerate(lines, 1):
        rows.append([str(i), code, d, str(q), fm(p), f"{r}%", fm(q * p)])
    t = Table(rows, colWidths=[22, 62, 190, 40, 70, 45, 80])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                           ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (3, 0), (-1, -1), "RIGHT")]))
    w, h = t.wrapOn(c, W, H); t.drawOn(c, 40, H - 240 - h)
    sub, tax, tot = compute(lines); y = H - 260 - h
    c.setFont("Helvetica", 10)
    for lab, val in [("Sub Total", sub), ("CGST @ 9%", tax / 2), ("SGST @ 9%", tax / 2), ("Grand Total", tot)]:
        c.drawString(340, y, lab); c.drawRightString(550, y, fm(val)); y -= 15
    c.save()

def layout_b(fn, v, inv_no, date, due, po, lines):
    """Borderless text layout, IGST, 'Amount Due', dd Mon yyyy dates."""
    c = canvas.Canvas(os.path.join(INV, fn), pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 16); c.drawRightString(W - 40, H - 50, v[0]); c.setFont("Helvetica", 9)
    c.drawRightString(W - 40, H - 64, v[2]); c.drawRightString(W - 40, H - 76, f"GSTIN {v[1]}")
    c.setFont("Helvetica-Bold", 22); c.drawString(40, H - 60, "Invoice")
    c.setFont("Helvetica", 10)
    for i, t in enumerate([f"Invoice #: {inv_no}", f"Invoice Date: {date}", f"Payment Due: {due}", f"P.O. Ref: {po}"]):
        c.drawString(40, H - 100 - i * 14, t)
    y = H - 190; c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Item  Description  Qty  Unit Price  Tax  Amount"); c.setFont("Helvetica", 10); y -= 18
    for i, (code, d, q, p, r) in enumerate(lines, 1):
        c.drawString(40, y, f"{i} {code} {d} {q} {fm(p)} {r}% {fm(q * p)}"); y -= 15
    sub, tax, tot = compute(lines); y -= 15
    for lab, val in [("Sub Total", sub), (f"IGST @ {lines[0][4]}%", tax), ("Amount Due", tot)]:
        c.drawString(300, y, f"{lab}   {fm(val)}"); y -= 15
    c.save()

def layout_c(fn, v, bill_no, date, due, po, lines):
    """Header band, ISO dates, 'Bill No', single GST line, TOTAL with rupee sign."""
    c = canvas.Canvas(os.path.join(INV, fn), pagesize=A4); W, H = A4
    c.setFillColor(colors.HexColor("#1e3a5f")); c.rect(0, H - 90, W, 90, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 20); c.drawString(40, H - 45, v[0])
    c.setFont("Helvetica", 9); c.drawString(40, H - 62, f"GSTIN: {v[1]}  |  {v[2]}")
    c.setFillColor(colors.black); c.setFont("Helvetica", 10)
    for i, t in enumerate([f"Bill No: {bill_no}", f"Invoice Date: {date}", f"Due Date: {due}", f"Purchase Order: {po}"]):
        c.drawString(40, H - 120 - i * 14, t)
    y = H - 200
    for i, (code, d, q, p, r) in enumerate(lines, 1):
        c.drawString(40, y, f"{i} {code} {d} {q} {fm(p)} {r}% {fm(q * p)}"); y -= 15
    sub, tax, tot = compute(lines); y -= 15
    c.drawString(300, y, f"Sub Total   {fm(sub)}"); y -= 15
    c.drawString(300, y, f"GST ({lines[0][4]}%)   {fm(tax)}"); y -= 15
    c.setFont("Helvetica-Bold", 11); c.drawString(300, y, f"TOTAL   INR {fm(tot)}")
    c.save()

def font(size):
    for f in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        try: return ImageFont.truetype(f, size)
        except OSError: continue
    return ImageFont.load_default(size)

def scanned(fn, v, inv_no, date, due, po, lines):
    """Image-only PDF: blurred, noisy, skewed, with an obscured PO number and due date."""
    random.seed(7)
    W, H = 1654, 2339; im = Image.new("L", (W, H), 255); d = ImageDraw.Draw(im)
    d.text((100, 120), v[0], font=font(48), fill=0); d.text((100, 190), f"GSTIN: {v[1]}", font=font(30), fill=0)
    d.text((100, 280), "TAX INVOICE", font=font(44), fill=0)
    rows = [f"Invoice No: {inv_no}", f"Invoice Date: {date}", f"Due Date: {due}", f"PO Number: {po}"]
    for i, t in enumerate(rows): d.text((100, 360 + i * 50), t, font=font(34), fill=0)
    y = 640
    for i, (code, dsc, q, p, r) in enumerate(lines, 1):
        d.text((100, y), f"{i} {code} {dsc} {q} {fm(p)} {r}% {fm(q * p)}", font=font(32), fill=0); y += 55
    sub, tax, tot = compute(lines); y += 40
    for lab, val in [("Sub Total", sub), (f"GST @ {lines[0][4]}%", tax), ("Grand Total", tot)]:
        d.text((800, y), f"{lab}   {fm(val)}", font=font(34), fill=0); y += 55
    # damage: smear PO number + due date, then global blur/noise/skew
    for box in [(100, 460, 900, 505), (100, 410, 700, 455)]:
        region = im.crop(box).filter(ImageFilter.GaussianBlur(14)); im.paste(region, box[:2])
    d.rectangle((420, 466, 560, 500), fill=90)  # coffee-stain style blot over part of the PO ref
    im = im.filter(ImageFilter.GaussianBlur(1.3)).rotate(1.4, fillcolor=255, expand=False)
    px = im.load()
    for _ in range(60000):
        x, y2 = random.randrange(W), random.randrange(H); px[x, y2] = max(0, px[x, y2] - random.randrange(80))
    im.convert("RGB").save(os.path.join(INV, fn), "PDF", resolution=200)

def upi(fn):
    im = Image.new("RGB", (720, 1280), (245, 247, 250)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 720, 140), fill=(76, 63, 160)); d.text((40, 50), "PayFast UPI", font=font(40), fill="white")
    d.ellipse((290, 200, 430, 340), fill=(46, 160, 90)); d.text((318, 232), "OK", font=font(60), fill="white")
    d.text((190, 380), "Payment Successful", font=font(42), fill=(30, 30, 30))
    d.text((230, 460), "₹ 10,000.00", font=font(64), fill=(0, 0, 0))
    d.text((60, 600), "To: Bluewave Logistics Pvt Ltd", font=font(30), fill=(60, 60, 60))
    d.text((60, 660), "Date: 10 Feb 2026, 11:42 AM", font=font(30), fill=(60, 60, 60))
    d.text((60, 740), "UPI Ref No: 412345678901", font=font(34), fill=(0, 0, 0))
    d.text((60, 800), "Transaction ID: PF20260210XYZ99", font=font(26), fill=(120, 120, 120))
    im.save(os.path.join(PAY, fn))

L = lambda *a: list(a)
# --- Apex: PO-1001 (Steel Widget 100 @1000 +18% = 118,000) and PO-1002 (Maintenance 100 @1000, 0% = 100,000)
layout_a("01_apex_INV-2026-0042_happy_path.pdf", VENDORS["apex"], "INV-2026-0042", "05/01/2026", "04/02/2026", "PO-1001", [("WID-01", "Steel Widget", 100, 1000, 18)])
layout_a("02_apex_APX-2026-101_po_part1.pdf", VENDORS["apex"], "APX/2026/101", "10/01/2026", "09/02/2026", "PO-1002", [("MNT-01", "Maintenance Service Hour", 40, 1000, 0)])
layout_a("03_apex_APX-2026-102_po_part2.pdf", VENDORS["apex"], "APX/2026/102", "20/01/2026", "19/02/2026", "PO-1002", [("MNT-01", "Maintenance Service Hour", 35, 1000, 0)])
layout_a("04_apex_APX-2026-103_po_overrun.pdf", VENDORS["apex"], "APX/2026/103", "30/01/2026", "01/03/2026", "PO-1002", [("MNT-01", "Maintenance Service Hour", 30, 1000, 0)])
# --- Bluewave: PO-2001 (Freight 100 @1000 +18%); invoice bills 1100 => price discrepancy
layout_b("05_bluewave_BWL-7788_price_discrepancy.pdf", VENDORS["blue"], "BWL-7788", "12 Feb 2026", "14 Mar 2026", "PO-2001", [("FRT-01", "Freight Charges Pallet", 100, 1100, 18)])
# --- Crestline: PO-3001 (chairs+lamps) digital, PO-3002 (paper) scanned
layout_c("06_crestline_CR-5001_happy_path.pdf", VENDORS["crest"], "CR-5001", "2026-02-20", "2026-03-22", "PO-3001",
         [("OFF-01", "Office Chair", 20, 5500, 18), ("OFF-02", "Desk Lamp", 50, 800, 18)])
scanned("07_crestline_CR-5002_poor_scan.pdf", VENDORS["crest"], "CR-5002", "25/02/2026", "27/03/2026", "PO-3002", [("PAP-01", "Printer Paper A4 Box", 200, 450, 12)])
upi("upi_payment_utr_412345678901.png")

cols = ["Supplier", "Bill Ref", "Bill Dt", "Payable By", "Purchase Order Ref", "Net Value", "GST Amt", "Gross Payable"]
rows = [
 ["Crestline Office Solutions Pvt Ltd", "CR 5001", "20-02-2026", "22-03-2026", "PO-3001", "150000", "27000", "177000"],   # duplicate of PDF #6 (normalised no.)
 ["Bluewave Logistics Pvt Ltd", "BWL-7790", "15-02-2026", "17-03-2026", "PO-2001", "20000", "3600", "23600"],
 ["Apex Industrial Supplies Pvt Ltd", "APX/2026/104", "01-03-2026", "31-03-2026", "PO-1001", "5000", "900", "5900"],
 ["Apex Industrial Supplies Pvt Ltd", "APX/2026/105", "31-02-2026", "", "PO-1001", "1000", "180", "1180"],   # invalid date
 ["Unknown Traders Ltd", "UT-1", "02-03-2026", "", "", "900", "162", "1062"],                                  # unknown vendor
 ["Bluewave Logistics Pvt Ltd", "", "03-03-2026", "", "PO-2001", "100", "18", "118"],                            # missing number
]
df = pd.DataFrame(rows, columns=cols)
df.to_csv(os.path.join(SHEET, "vendor_bills_nonstandard_columns.csv"), index=False)
df.to_excel(os.path.join(SHEET, "vendor_bills_nonstandard_columns.xlsx"), index=False)
pd.DataFrame([
 ["PO-1001", "Apex Industrial Supplies Pvt Ltd", "WID-01 Steel Widget", 100, 1000, 18, 118000],
 ["PO-1002", "Apex Industrial Supplies Pvt Ltd", "MNT-01 Maintenance Service Hour", 100, 1000, 0, 100000],
 ["PO-2001", "Bluewave Logistics Pvt Ltd", "FRT-01 Freight Charges Pallet", 100, 1000, 18, 118000],
 ["PO-2002", "Bluewave Logistics Pvt Ltd", "FRT-02 Warehouse Handling Hour", 50, 2000, 0, 100000],
 ["PO-3001", "Crestline Office Solutions Pvt Ltd", "OFF-01 Office Chair x20 @5500; OFF-02 Desk Lamp x50 @800", "", "", 18, 177000],
 ["PO-3002", "Crestline Office Solutions Pvt Ltd", "PAP-01 Printer Paper A4 Box", 200, 450, 12, 100800],
 ["PO-4001", "Bluewave Logistics Pvt Ltd", "FRT-01 Freight Charges Pallet (CANCELLED PO)", 10, 1000, 18, 11800],
], columns=["PO", "Vendor", "Items", "Qty", "Unit Price", "Tax %", "PO Total"]).to_csv(os.path.join(PO, "purchase_orders_reference.csv"), index=False)
print("Sample data written to", os.path.abspath(ROOT))
