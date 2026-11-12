import { useEffect, useState } from 'react'
import { get, put } from '../api'
import { Badge, Btn, Card, ErrorBox, Input, PageHeader, useLoad } from '../ui'

const LABELS: Record<string, string> = { abs_amount: 'Absolute amount tolerance (currency units)', pct_amount: 'Percentage amount tolerance (%)', po_overrun_abs: 'PO overrun allowance — absolute', po_overrun_pct: 'PO overrun allowance — % of remaining PO value',
  price_variance_pct: 'Unit-price variance vs PO (%)', min_field_confidence: 'Minimum field confidence (0–1)' }
export default function SettingsPage() {
  const t = useLoad(() => get('/api/settings/tolerances')); const h = useLoad(() => get('/api/health'))
  const [v, setV] = useState<any>({}); const [msg, setMsg] = useState<string | null>(null); const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (t.data) setV(t.data) }, [t.data])
  const save = async () => { setErr(null); setMsg(null); try { setV(await put('/api/settings/tolerances', v)); setMsg('Saved. Applies to the next processing run.') } catch (e: any) { setErr(e.message) } }
  return (<><PageHeader title="Settings" sub="Tolerance policy used by the deterministic rule engine" />
    <div className="grid gap-5 lg:grid-cols-2">
      <Card title="Tolerances"><div className="space-y-3">{Object.keys(LABELS).map(k => <Input key={k} label={LABELS[k]} value={v[k] ?? ''} onChange={(e: any) => setV({ ...v, [k]: e.target.value })} />)}</div>
        <div className="mt-3"><ErrorBox msg={err} />{msg && <p className="text-sm text-emerald-600">{msg}</p>}</div><div className="mt-3"><Btn onClick={save}>Save tolerances</Btn></div></Card>
      <Card title="System health">{h.data && <ul className="space-y-3 text-sm">
        <li className="flex justify-between">Backend + database <Badge v={h.data.database.ok ? 'COMPLETED' : 'FAILED'} /></li>{h.data.database.error && <li className="text-xs text-red-600">{h.data.database.error}</li>}
        <li className="flex justify-between">Tesseract OCR <Badge v={h.data.ocr.ok ? 'COMPLETED' : 'WARNING'} /></li>
        <li className="flex justify-between">Ollama LLM (optional) <Badge v={h.data.llm.ok ? 'COMPLETED' : 'INFO'} /></li>
        {!h.data.llm.ok && <li className="text-xs text-slate-500">Without a local LLM, deterministic extraction is used and uncertain fields go to review.</li>}</ul>}
        {h.err && <ErrorBox msg={'Backend unreachable: ' + h.err} />}</Card>
    </div></>)
}
