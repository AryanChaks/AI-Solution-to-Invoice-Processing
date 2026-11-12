import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, CircleDashed, Loader2, XCircle, AlertTriangle, MinusCircle } from 'lucide-react'
import { get } from '../api'
import { Badge, Card, ErrorBox, PageHeader, Spinner } from '../ui'

const ICON: any = { COMPLETED: <CheckCircle2 className="h-5 w-5 text-emerald-500" />, RUNNING: <Loader2 className="h-5 w-5 animate-spin text-blue-500" />,
  FAILED: <XCircle className="h-5 w-5 text-red-500" />, REVIEW_REQUIRED: <AlertTriangle className="h-5 w-5 text-amber-500" />, PENDING: <CircleDashed className="h-5 w-5 text-slate-300" />, SKIPPED: <MinusCircle className="h-5 w-5 text-slate-300" /> }

export default function RunView() {
  const { id } = useParams(); const [stages, setStages] = useState<any[]>([]); const [events, setEvents] = useState<Record<string, any>>({})
  const [run, setRun] = useState<any>(null); const [done, setDone] = useState(false); const [err, setErr] = useState<string | null>(null)
  const loadRun = () => get(`/api/processing/runs/${id}`).then(setRun).catch(e => setErr(e.message))
  useEffect(() => {
    get('/api/processing/stages').then(setStages); loadRun()
    // Real backend events over SSE; the server replays history first, so reconnecting or opening a finished run works too.
    const es = new EventSource(`/api/processing/runs/${id}/stream`)
    es.addEventListener('stage', (m: any) => { const e = JSON.parse(m.data); setEvents(p => ({ ...p, [e.Stage_Name]: e })) })
    es.addEventListener('done', () => { setDone(true); es.close(); loadRun() })
    es.addEventListener('error', () => { /* browser retries automatically while running */ })
    return () => es.close()
  }, [id])
  const d = run?.detail; const dec = d?.decision
  return (<>
    <PageHeader title={`Processing run #${id}`} sub={run ? `${run.Source_Type} · ${run.Uploaded_File_Name || 'direct entry'} · ${run.Doc_Type || ''}` : ''}>
      {run?.Invoice_ID && <Link className="rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white" to={`/invoices/${run.Invoice_ID}`}>Open invoice</Link>}
      {run?.Review_Status === 'PENDING' && <Link className="rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2 text-sm font-medium text-amber-800" to={`/review/${id}`}>Go to review</Link>}
    </PageHeader>
    <ErrorBox msg={err} />
    <div className="grid gap-5 lg:grid-cols-5">
      <Card title="Execution timeline" className="lg:col-span-2">
        <ol className="space-y-3">{stages.map(s => { const e = events[s.name]; const st = e ? e.Stage_Status : (done ? 'SKIPPED' : 'PENDING')
          return <li key={s.name} className="flex gap-3"><div className="pt-0.5">{ICON[st] || ICON.PENDING}</div>
            <div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2"><span className={`text-sm font-medium ${st === 'PENDING' || st === 'SKIPPED' ? 'text-slate-400' : ''}`}>{s.label}</span>
              <span className="text-xs text-slate-400">{st === 'SKIPPED' ? 'not applicable' : e?.Duration != null ? `${Number(e.Duration).toFixed(2)}s` : ''}</span></div>
              {e?.Output_Summary && <p className="mt-0.5 break-words text-xs text-slate-500">{e.Output_Summary}</p>}
              {e?.Error_Message && <p className="mt-0.5 break-words text-xs text-red-600">{e.Error_Message}</p>}</div></li> })}</ol>
        {!done && <div className="mt-4 flex items-center gap-2 text-xs text-blue-600"><Loader2 className="h-3 w-3 animate-spin" />Live from backend…</div>}
      </Card>
      <div className="space-y-5 lg:col-span-3">
        {!run || !dec ? <Card title="Decision">{done ? <Spinner /> : <p className="text-sm text-slate-500">Waiting for the workflow to finish…</p>}</Card> : <>
          <Card title="Final decision" right={<Badge v={dec.status} />}>
            <p className="text-sm">{dec.explanation}</p><p className="mt-2 text-sm text-slate-600"><b>Next action:</b> {dec.next_action}</p>
            {d.dup && <p className="mt-2 text-sm"><b>Invoice identification:</b> <Badge v={d.dup.outcome} /> <span className="text-slate-600">{d.dup.reasons?.join('; ')}</span></p>}
            {d.vendor?.name && <p className="mt-2 text-sm"><b>Vendor:</b> {d.vendor.name} <span className="text-slate-500">({d.vendor.reason})</span></p>}
            {d.po && <p className="mt-2 text-sm"><b>PO:</b> {d.po.po_number} <span className="text-slate-500">({d.po.how})</span></p>}
          </Card>
          <div className="grid gap-5 md:grid-cols-2">
            <Card title={`Rules passed (${dec.passed.length})`}><ul className="space-y-1 text-sm">{dec.passed.map((p: string) => <li key={p} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />{p}</li>)}</ul></Card>
            <Card title={`Rules failed (${dec.failed.length})`}>{dec.failed.length === 0 ? <p className="text-sm text-slate-500">None</p> : <ul className="space-y-1 text-sm">{dec.failed.map((p: string, i: number) => <li key={i} className="flex gap-2"><XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" /><span className="break-words">{p}</span></li>)}</ul>}</Card>
          </div>
          {d.candidates?.length > 0 && <Card title="PO candidates (ranking only)"><ul className="space-y-2 text-sm">{d.candidates.map((c: any) => <li key={c.po_id}><b>{c.po_number}</b> — score {c.score} <span className="text-xs text-slate-500">({c.parts.join('; ')})</span></li>)}</ul></Card>}
          {d.consumption?.po_total && <Card title="PO consumption"><p className="text-sm">PO total {d.consumption.po_total} · invoiced before {d.consumption.invoiced_before} · remaining before {d.consumption.remaining_before} · remaining after this invoice {d.consumption.remaining_after}</p></Card>}
          {d.recon?.steps?.length > 0 && <Card title="Financial reconciliation (Decimal arithmetic)"><ul className="space-y-1 font-mono text-xs text-slate-600">{d.recon.steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul><p className="mt-2 text-sm">Expected total {d.recon.expected_total} · difference {d.recon.difference}</p></Card>}
          {d.payment_error && <ErrorBox msg={'Payment not recorded: ' + d.payment_error} />}
        </>}
      </div>
    </div></>)
}
