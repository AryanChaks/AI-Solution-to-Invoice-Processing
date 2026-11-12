import { Link } from 'react-router-dom'
import { get, money, dt } from '../api'
import { Badge, Card, ErrorBox, PageHeader, Table, useLoad } from '../ui'

export default function Review() {
  const { data, err } = useLoad(() => get('/api/reviews'))
  return (<><PageHeader title="Review Queue" sub="Invoices that automation could not safely approve" /><ErrorBox msg={err} />
    <Card><Table head={['Run', 'Invoice', 'Vendor', 'Amount', 'Issue', 'Severity', 'Processed', '']} empty={data && !data.length ? 'Nothing to review 🎉' : ''}>
      {(data || []).map((r: any) => <tr key={r.Run_ID} className="hover:bg-slate-50"><td className="px-3 py-2">#{r.Run_ID}</td><td className="px-3 py-2 font-medium">{r.Invoice_Number || '— (unresolved)'}</td><td className="px-3 py-2">{r.Vendor_Name || '—'}</td>
        <td className="px-3 py-2">{money(r.Total_Amount)}</td><td className="max-w-sm break-words px-3 py-2 text-xs text-slate-600">{r.issue}{r.reasons.length > 1 ? ` (+${r.reasons.length - 1} more)` : ''}</td>
        <td className="px-3 py-2"><Badge v={r.severity} /></td><td className="px-3 py-2 text-xs">{dt(r.Started_At)}</td><td className="px-3 py-2"><Link className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white" to={`/review/${r.Run_ID}`}>Review</Link></td></tr>)}</Table></Card></>)
}
