import { useState } from 'react'
import { Link } from 'react-router-dom'
import { get, dt } from '../api'
import { Badge, Card, ErrorBox, Input, PageHeader, Select, Table, useLoad } from '../ui'

export default function HistoryPage() {
  const [f, setF] = useState<any>({ decision: '', source: '', status: '', vendor_id: '', date_from: '', date_to: '' })
  const vendors = useLoad(() => get('/api/vendors'))
  const qs = Object.entries(f).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
  const { data, err } = useLoad(() => get('/api/processing/runs?' + qs), [qs])
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value })
  return (<><PageHeader title="Processing History" sub="Every run is persisted with its full event timeline" /><ErrorBox msg={err} />
    <Card><div className="mb-4 grid gap-3 md:grid-cols-6">
      <Input label="From" type="date" value={f.date_from} onChange={set('date_from')} /><Input label="To" type="date" value={f.date_to} onChange={set('date_to')} />
      <Select label="Vendor" value={f.vendor_id} onChange={set('vendor_id')}><option value="">All</option>{(vendors.data || []).map((v: any) => <option key={v.Vendor_ID} value={v.Vendor_ID}>{v.Vendor_Name}</option>)}</Select>
      <Select label="Decision" value={f.decision} onChange={set('decision')}><option value="">All</option>{['AUTO_APPROVED_FOR_AP', 'REVIEW_REQUIRED', 'BLOCKED', 'FAILED'].map(s => <option key={s}>{s}</option>)}</Select>
      <Select label="Method" value={f.source} onChange={set('source')}><option value="">All</option>{['PDF', 'IMAGE', 'EXCEL', 'MANUAL'].map(s => <option key={s}>{s}</option>)}</Select>
      <Select label="Status" value={f.status} onChange={set('status')}><option value="">All</option>{['RUNNING', 'COMPLETED', 'FAILED'].map(s => <option key={s}>{s}</option>)}</Select></div>
      <Table head={['Run', 'Invoice', 'Vendor', 'Method', 'Started', 'Duration', 'Decision', 'Status', 'Review']} empty={data && !data.length ? 'No runs match.' : ''}>
        {(data || []).map((r: any) => <tr key={r.Run_ID} className="hover:bg-slate-50"><td className="px-3 py-2"><Link className="font-medium text-brand-600" to={`/runs/${r.Run_ID}`}>#{r.Run_ID}</Link></td>
          <td className="px-3 py-2">{r.Invoice_ID ? <Link className="text-brand-600" to={`/invoices/${r.Invoice_ID}`}>{r.Invoice_Number}</Link> : (r.Invoice_Number || '—')}</td><td className="px-3 py-2">{r.Vendor_Name || '—'}</td><td className="px-3 py-2">{r.Source_Type}</td>
          <td className="whitespace-nowrap px-3 py-2 text-xs">{dt(r.Started_At)}</td><td className="px-3 py-2">{r.Processing_Duration != null ? `${Number(r.Processing_Duration).toFixed(2)}s` : '—'}</td><td className="px-3 py-2"><Badge v={r.Final_Decision} /></td><td className="px-3 py-2"><Badge v={r.Processing_Status} /></td><td className="px-3 py-2"><Badge v={r.Review_Status} /></td></tr>)}</Table></Card></>)
}
