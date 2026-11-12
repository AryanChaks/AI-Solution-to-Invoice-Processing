import { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Trash2, Upload, FileSpreadsheet, FileUp, PenLine, ImageUp } from 'lucide-react'
import { get, post, money } from '../api'
import { Badge, Btn, Card, ErrorBox, Input, PageHeader, Select, Table, useLoad } from '../ui'

const TABS = [['manual', 'Single Invoice', PenLine], ['excel', 'Excel / CSV', FileSpreadsheet], ['pdf', 'PDF / Scan', FileUp]] as const
export default function AddInvoice() {
  const [tab, setTab] = useState<string>('pdf')
  return (<>
    <PageHeader title="Add Invoice" sub="Every method runs the same validation workflow. You never have to say whether an invoice is new — it is identified automatically." />
    <div className="mb-5 inline-flex rounded-xl border border-slate-200 bg-white p-1">
      {TABS.map(([k, l, I]) => <button key={k} onClick={() => setTab(k)} className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ${tab === k ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}><I className="h-4 w-4" />{l}</button>)}
    </div>
    {tab === 'manual' && <Manual />}{tab === 'excel' && <Excel />}{tab === 'pdf' && <Pdf />}
  </>)
}

/* ---------------- PDF ---------------- */
function Pdf() {
  const nav = useNavigate(); const [files, setFiles] = useState<File[]>([]); const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true); setErr(null)
    try {
      const fd = new FormData(); files.forEach(f => fd.append('files', f))
      const r = await post('/api/invoices/upload/pdf', fd)
      if (r.length === 1) nav(`/runs/${r[0].run_id}`); else nav('/history')
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return <Card title="Upload invoice documents">
    <p className="mb-4 text-sm text-slate-500">Digital PDFs are read directly (no OCR). Scanned PDFs and images are sent to Tesseract OCR automatically. PDF, PNG, JPG, TIFF — up to the configured size limit.</p>
    <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 px-6 py-12 text-slate-500 hover:border-brand-500 hover:bg-brand-50">
      <Upload className="h-8 w-8" /><span className="text-sm font-medium">{files.length ? files.map(f => f.name).join(', ') : 'Click to choose one or more files'}</span>
      <input type="file" className="hidden" multiple accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff" onChange={e => setFiles(Array.from(e.target.files || []))} /></label>
    <div className="mt-4 space-y-3"><ErrorBox msg={err} /><Btn disabled={!files.length || busy} onClick={submit}>{busy ? 'Uploading…' : 'Process invoice'}</Btn></div>
  </Card>
}

/* ---------------- Manual ---------------- */
const emptyLine = () => ({ description: '', item_code: '', quantity: '1', unit_price: '0', tax_rate: '0' })
function Manual() {
  const vendors = useLoad(() => get('/api/vendors'))
  const [f, setF] = useState<any>({ vendor_id: '', invoice_number: '', invoice_date: '', due_date: '', po_number: '', currency: 'INR', subtotal: '', tax: '', discount: '0', other: '0', total: '', notes: '' })
  const [lines, setLines] = useState<any[]>([emptyLine()]); const [withPay, setWithPay] = useState(false)
  const [pay, setPay] = useState<any>({ amount: '', date: '', method: 'UPI', ref: '', image_amount: '' })
  const [upi, setUpi] = useState<any>(null); const [res, setRes] = useState<any>(null); const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false)
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value })
  const calc = lines.reduce((a, l) => a + (Number(l.quantity) || 0) * (Number(l.unit_price) || 0), 0)
  const calcTax = lines.reduce((a, l) => a + (Number(l.quantity) || 0) * (Number(l.unit_price) || 0) * (Number(l.tax_rate) || 0) / 100, 0)
  const autofill = () => setF({ ...f, subtotal: calc.toFixed(2), tax: calcTax.toFixed(2), total: (calc + calcTax + Number(f.other || 0) - Number(f.discount || 0)).toFixed(2) })

  const readImage = async (file?: File) => {
    if (!file) return; setErr(null); setUpi(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await post('/api/invoices/payment-image', fd); setUpi(r)
      setPay((p: any) => ({ ...p, ref: r.utr || p.ref, amount: r.amount || p.amount, image_amount: r.amount || '' }))
    } catch (e: any) { setErr('Could not read the image: ' + e.message + ' — you can still enter the details manually.') }
  }
  const submit = async () => {
    setBusy(true); setErr(null); setRes(null)
    try {
      const body: any = { ...f, vendor_id: f.vendor_id ? Number(f.vendor_id) : null, lines: lines.filter(l => l.description), payment: withPay && (pay.amount || pay.ref) ? pay : null }
      Object.keys(body).forEach(k => body[k] === '' && (body[k] = null))
      setRes(await post('/api/invoices/manual', body))
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  return <div className="space-y-5">
    <Card title="Invoice header"><div className="grid gap-4 md:grid-cols-3">
      <Select label="Vendor *" value={f.vendor_id} onChange={set('vendor_id')}><option value="">Select vendor…</option>{(vendors.data || []).map((v: any) => <option key={v.Vendor_ID} value={v.Vendor_ID}>{v.Vendor_Name}{v.Is_Approved ? '' : ' (unapproved)'}</option>)}</Select>
      <Input label="Invoice number *" value={f.invoice_number} onChange={set('invoice_number')} />
      <Input label="PO number" value={f.po_number} onChange={set('po_number')} placeholder="e.g. PO-1001" />
      <Input label="Invoice date *" type="date" value={f.invoice_date} onChange={set('invoice_date')} />
      <Input label="Due date" type="date" value={f.due_date} onChange={set('due_date')} />
      <Select label="Currency" value={f.currency} onChange={set('currency')}><option>INR</option><option>USD</option><option>EUR</option></Select>
      <Input label="Subtotal" value={f.subtotal} onChange={set('subtotal')} /><Input label="Tax amount" value={f.tax} onChange={set('tax')} />
      <Input label="Discount" value={f.discount} onChange={set('discount')} /><Input label="Other charges" value={f.other} onChange={set('other')} />
      <Input label="Total invoice amount *" value={f.total} onChange={set('total')} /><Input label="Notes" value={f.notes} onChange={set('notes')} />
    </div></Card>
    <Card title="Line items" right={<div className="flex gap-2"><Btn variant="ghost" onClick={autofill}>Fill totals from lines</Btn><Btn variant="ghost" onClick={() => setLines([...lines, emptyLine()])}><Plus className="h-4 w-4" />Add line</Btn></div>}>
      <div className="space-y-2">{lines.map((l, i) => <div key={i} className="grid grid-cols-12 items-end gap-2">
        <div className="col-span-4"><Input label={i === 0 ? 'Description' : ''} value={l.description} onChange={(e: any) => setLines(lines.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} /></div>
        {(['item_code', 'quantity', 'unit_price', 'tax_rate'] as const).map((k, n) => <div key={k} className="col-span-2"><Input label={i === 0 ? ['Item code', 'Qty', 'Unit price', 'Tax %'][n] : ''} value={l[k]} onChange={(e: any) => setLines(lines.map((x, j) => j === i ? { ...x, [k]: e.target.value } : x))} /></div>)}
        <div className="col-span-1 pb-2 text-right text-xs text-slate-500">{money((Number(l.quantity) || 0) * (Number(l.unit_price) || 0))}</div>
        <button className="col-span-1 pb-2 text-slate-400 hover:text-red-600" onClick={() => setLines(lines.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></button></div>)}</div>
      <p className="mt-3 text-xs text-slate-500">Computed subtotal {money(calc)} · tax {money(calcTax)}</p>
    </Card>
    <Card title="Payment (optional)" right={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={withPay} onChange={e => setWithPay(e.target.checked)} />Record a payment</label>}>
      {!withPay ? <p className="text-sm text-slate-500">No payment will be created unless you tick this box and supply payment details.</p> : <div className="space-y-4">
        <div className="rounded-lg border border-dashed border-slate-300 p-4"><label className="flex cursor-pointer items-center gap-3 text-sm text-slate-600"><ImageUp className="h-5 w-5" />Upload UPI payment screenshot to extract the UTR and amount (optional)
          <input type="file" accept="image/*" className="hidden" onChange={e => readImage(e.target.files?.[0])} /></label>
          {upi && <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">OCR read — UTR: <b>{upi.utr || 'not found'}</b> · Amount: <b>{upi.amount || 'not found'}</b> · OCR confidence {(upi.ocr_confidence * 100).toFixed(0)}%. Please verify below; anything missing can be typed in.</div>}</div>
        <div className="grid gap-4 md:grid-cols-4"><Input label="UTR / reference" value={pay.ref} onChange={(e: any) => setPay({ ...pay, ref: e.target.value })} />
          <Input label="Amount" value={pay.amount} onChange={(e: any) => setPay({ ...pay, amount: e.target.value })} />
          <Input label="Payment date" type="date" value={pay.date} onChange={(e: any) => setPay({ ...pay, date: e.target.value })} />
          <Select label="Method" value={pay.method} onChange={(e: any) => setPay({ ...pay, method: e.target.value })}><option>UPI</option><option>NEFT</option><option>RTGS</option><option>CHEQUE</option><option>CASH</option></Select></div></div>}
    </Card>
    <ErrorBox msg={err} />
    <Btn disabled={busy} onClick={submit}>{busy ? 'Processing…' : 'Submit & validate'}</Btn>
    {res && <Card title="Result"><div className="flex items-center gap-3"><Badge v={res.decision} /><span className="text-sm">{res.detail?.decision?.explanation}</span></div>
      {res.detail?.payment_error && <div className="mt-3"><ErrorBox msg={'Payment not recorded: ' + res.detail.payment_error} /></div>}
      <div className="mt-3 flex gap-3 text-sm"><Link className="text-brand-600" to={`/runs/${res.run_id}`}>View processing timeline</Link>{res.invoice_id && <Link className="text-brand-600" to={`/invoices/${res.invoice_id}`}>Open invoice</Link>}</div></Card>}
  </div>
}

/* ---------------- Excel ---------------- */
function Excel() {
  const [file, setFile] = useState<File | null>(null); const [pre, setPre] = useState<any>(null); const [fields, setFields] = useState<any[]>([])
  const [map, setMap] = useState<any>({}); const [out, setOut] = useState<any>(null); const [err, setErr] = useState<string | null>(null); const [tname, setTname] = useState(''); const [busy, setBusy] = useState(false)
  const choose = async (f?: File) => {
    if (!f) return; setFile(f); setErr(null); setOut(null); setPre(null)
    try { const fd = new FormData(); fd.append('file', f); const [p, fl] = await Promise.all([post('/api/invoices/upload/excel/preview', fd), get('/api/invoices/mapping-fields')]); setPre(p); setFields(fl); setMap(p.suggested) }
    catch (e: any) { setErr(e.message) }
  }
  const run = async (dry: boolean) => {
    if (!file) return; setBusy(true); setErr(null)
    try { const fd = new FormData(); fd.append('file', file); fd.append('mapping', JSON.stringify(map)); fd.append('dry_run', String(dry)); if (tname && !dry) fd.append('template_name', tname); setOut(await post('/api/invoices/upload/excel/commit', fd)) }
    catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const missing = fields.filter(f => f.required && !map[f.key])
  return <div className="space-y-5">
    <Card title="Upload spreadsheet"><label className="flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed border-slate-300 px-6 py-8 text-slate-500 hover:border-brand-500">
      <FileSpreadsheet className="h-6 w-6" /><span className="text-sm">{file ? file.name : 'Choose .xlsx, .xls or .csv'}</span><input type="file" className="hidden" accept=".xlsx,.xls,.csv" onChange={e => choose(e.target.files?.[0])} /></label>
      <div className="mt-3"><ErrorBox msg={err} /></div></Card>
    {pre && <>
      <Card title="Map your columns" right={pre.templates.length > 0 && <Select value="" onChange={(e: any) => { const t = pre.templates.find((x: any) => String(x.id) === e.target.value); if (t) setMap(t.mapping) }}><option value="">Load saved template…</option>{pre.templates.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}</Select>}>
        <div className="grid gap-3 md:grid-cols-2">{fields.map(f => <div key={f.key} className="flex items-center gap-3"><span className={`w-56 text-sm ${f.required && !map[f.key] ? 'font-medium text-red-600' : ''}`}>{f.label}{f.required && ' *'}</span>
          <Select value={map[f.key] || ''} onChange={(e: any) => setMap({ ...map, [f.key]: e.target.value })}><option value="">— not mapped —</option>{pre.columns.map((c: string) => <option key={c}>{c}</option>)}</Select></div>)}</div>
        {missing.length > 0 && <p className="mt-3 text-sm text-red-600">Required fields not mapped: {missing.map(m => m.label).join(', ')}</p>}
      </Card>
      <Card title={`Preview (first ${pre.preview.length} of ${pre.rows} rows)`}><div className="overflow-x-auto"><Table head={pre.columns}>{pre.preview.map((r: any, i: number) => <tr key={i}>{pre.columns.map((c: string) => <td key={c} className="whitespace-nowrap px-3 py-1.5">{r[c]}</td>)}</tr>)}</Table></div></Card>
      <div className="flex flex-wrap items-end gap-3"><Btn variant="ghost" disabled={busy || missing.length > 0} onClick={() => run(true)}>Dry run (validate only)</Btn>
        <Input label="Save mapping as template (optional)" value={tname} onChange={(e: any) => setTname(e.target.value)} className="w-64" />
        <Btn disabled={busy || missing.length > 0 || !out?.dry_run} onClick={() => run(false)}>Import valid rows</Btn>{!out?.dry_run && <span className="text-xs text-slate-500">Run a dry run first</span>}</div>
    </>}
    {out && <Card title={out.dry_run ? 'Dry-run result (nothing saved)' : 'Import result'}>
      <p className="mb-3 text-sm">{out.total_rows} rows · <b className="text-emerald-600">{out.ok_rows} ok</b> · <b className="text-red-600">{out.error_rows} with errors</b></p>
      <Table head={['Row', 'Invoice', 'Vendor', 'Status', 'Details']}>{out.results.map((r: any) => <tr key={r.row}><td className="px-3 py-2">{r.row}</td><td className="px-3 py-2">{r.invoice_number || '—'}</td><td className="px-3 py-2">{r.vendor || '—'}</td>
        <td className="px-3 py-2"><Badge v={r.status} /></td><td className="px-3 py-2 text-xs text-slate-600">{r.errors?.length ? r.errors.join('; ') : r.decision ? <span><Badge v={r.decision} /> <Link className="text-brand-600" to={`/runs/${r.run_id}`}>run #{r.run_id}</Link></span> : r.dup ? `${r.dup}${r.existing_invoice_id ? ' of invoice #' + r.existing_invoice_id : ''}` : ''}</td></tr>)}</Table></Card>}
  </div>
}
