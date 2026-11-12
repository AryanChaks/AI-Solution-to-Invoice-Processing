import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { get, post, money } from '../api'
import DocViewer from '../DocViewer'
import { Badge, Btn, Card, ErrorBox, Input, PageHeader, Select, Spinner, useLoad } from '../ui'

const FIELDS = ['invoice_number', 'vendor_name', 'invoice_date', 'due_date', 'po_number', 'currency', 'subtotal', 'tax', 'discount', 'other', 'total']
export default function ReviewDetail() {
  const { runId } = useParams(); const nav = useNavigate()
  const run = useLoad(() => get(`/api/processing/runs/${runId}`), [runId]); const vendors = useLoad(() => get('/api/vendors')); const pos = useLoad(() => get('/api/purchase-orders'))
  const [edit, setEdit] = useState<any>({}); const [lines, setLines] = useState<any[] | null>(null); const [vendorId, setVendorId] = useState(''); const [poId, setPoId] = useState('')
  const [reason, setReason] = useState(''); const [err, setErr] = useState<string | null>(null); const [active, setActive] = useState<string | null>(null); const [busy, setBusy] = useState(false)
  if (run.err) return <ErrorBox msg={run.err} />; if (!run.data) return <Spinner />
  const r = run.data; const d = r.detail; const inv = r.parsed?.invoice || {}; const ev: any = Object.fromEntries((r.evidence || []).map((e: any) => [e.Field_Name, e]))
  const curLines = lines ?? r.parsed?.lines ?? []
  const act = async (kind: string) => {
    setBusy(true); setErr(null)
    try {
      if (kind === 'correct') {
        const corrections: any = {}
        Object.entries(edit).forEach(([k, v]) => { if (v !== (inv[k] ?? '')) corrections[k] = v })
        if (lines) corrections.lines = lines
        if (vendorId) corrections.vendor_id = Number(vendorId)
        if (poId) corrections.po_id = Number(poId)
        const x = await post(`/api/reviews/${runId}/correct`, { corrections, reason }); nav(`/runs/${x.run_id}`)
      } else { await post(`/api/reviews/${runId}/${kind}`, { reason }); nav('/review') }
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const ok = reason.trim().length >= 5
  return (<>
    <PageHeader title={`Review · run #${runId}`} sub={`${r.Invoice_Number || 'unresolved invoice'} · ${r.Vendor_Name || 'unknown vendor'}`}><Badge v={r.Final_Decision} /><Badge v={r.Review_Status} /></PageHeader>
    <div className="grid gap-5 xl:grid-cols-2">
      <div>{r.has_file ? <Card title="Original document"><DocViewer runId={r.Run_ID} evidence={r.evidence || []} active={active} /></Card> : <Card title="Original document"><p className="text-sm text-slate-500">No file attached to this run.</p></Card>}</div>
      <div className="space-y-5">
        <Card title="Why this needs review"><p className="text-sm">{d?.decision?.explanation}</p>
          <ul className="mt-2 space-y-1 text-sm text-red-700">{(d?.decision?.failed || []).map((f: string, i: number) => <li key={i}>• {f}</li>)}</ul>
          {d?.dup?.invoice_id && <p className="mt-2 text-sm">Existing invoice: <Link className="text-brand-600" to={`/invoices/${d.dup.invoice_id}`}>#{d.dup.invoice_id}</Link> — {d.dup.reasons?.join('; ')}</p>}
          {d?.consumption?.po_total && <p className="mt-2 text-sm text-slate-600">PO {d.po?.po_number}: total {d.consumption.po_total}, remaining before {d.consumption.remaining_before}, after {d.consumption.remaining_after}</p>}
          {d?.candidates?.length > 0 && <p className="mt-2 text-sm text-slate-600">PO candidates: {d.candidates.map((c: any) => `${c.po_number} (${c.score})`).join(', ')}</p>}
          <Link className="mt-3 inline-block text-sm text-brand-600" to={`/runs/${runId}`}>View full processing log →</Link></Card>
        <Card title="Extracted fields (editable)">
          <div className="grid gap-3 md:grid-cols-2">{FIELDS.map(f => { const e = ev[f]; return <div key={f} onFocus={() => setActive(f)}>
            <Input label={`${f}${e ? ` · ${(e.Confidence_Score * 100).toFixed(0)}% · ${e.Extraction_Method}` : ''}`} value={edit[f] ?? inv[f] ?? ''} onChange={(x: any) => setEdit({ ...edit, [f]: x.target.value })}
              className={e && e.Confidence_Score < 0.75 ? 'border-amber-400 bg-amber-50' : ''} /></div> })}</div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Select label="Set vendor explicitly" value={vendorId} onChange={(e: any) => setVendorId(e.target.value)}><option value="">(keep current)</option>{(vendors.data || []).map((v: any) => <option key={v.Vendor_ID} value={v.Vendor_ID}>{v.Vendor_Name}</option>)}</Select>
            <Select label="Select PO manually" value={poId} onChange={(e: any) => setPoId(e.target.value)}><option value="">(keep current)</option>{(pos.data || []).map((p: any) => <option key={p.PO_ID} value={p.PO_ID}>{p.PO_Number} · {p.Vendor_Name} · remaining {money(p.summary.remaining)}</option>)}</Select></div>
          <h4 className="mb-2 mt-4 text-xs font-semibold uppercase text-slate-500">Line items</h4>
          {curLines.map((l: any, i: number) => <div key={i} className="mb-2 grid grid-cols-12 gap-2">{['description', 'item_code', 'quantity', 'unit_price', 'tax_rate'].map(k => <div key={k} className={k === 'description' ? 'col-span-4' : 'col-span-2'}><Input value={l[k] ?? ''} onChange={(x: any) => setLines(curLines.map((y: any, j: number) => j === i ? { ...y, [k]: x.target.value } : y))} placeholder={k} /></div>)}</div>)}
          <Btn variant="ghost" onClick={() => setLines([...curLines, { description: '', item_code: '', quantity: '1', unit_price: '0', tax_rate: '0' }])}>+ line</Btn>
        </Card>
        <Card title="Decision (reason required, saved to audit trail)"><textarea className="w-full rounded-lg border border-slate-300 p-3 text-sm" rows={3} placeholder="Explain your decision (min 5 characters)…" value={reason} onChange={e => setReason(e.target.value)} />
          <div className="mt-3"><ErrorBox msg={err} /></div>
          <div className="mt-3 flex flex-wrap gap-2"><Btn variant="ok" disabled={!ok || busy} onClick={() => act('approve')}>Approve</Btn><Btn variant="danger" disabled={!ok || busy} onClick={() => act('reject')}>Reject</Btn>
            <Btn variant="ghost" disabled={!ok || busy} onClick={() => act('clarify')}>Request clarification</Btn><Btn disabled={!ok || busy} onClick={() => act('correct')}>Save corrections & reprocess</Btn></div></Card>
      </div></div></>)
}
