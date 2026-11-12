import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, CartesianGrid } from 'recharts'
import { FileText, CheckCircle2, ClipboardCheck, ShieldAlert, Copy, IndianRupee, Wallet, Timer, Target, Plus } from 'lucide-react'
import { get, money, dt } from '../api'
import { Badge, Btn, Card, ErrorBox, PageHeader, Spinner, Stat, Table, useLoad } from '../ui'

const C: any = { AUTO_APPROVED_FOR_AP: '#10b981', REVIEW_REQUIRED: '#f59e0b', BLOCKED: '#ef4444', FAILED: '#64748b', REJECTED: '#b91c1c', RUNNING: '#3b82f6' }

export default function Dashboard() {
  const s = useLoad(() => get('/api/dashboard/summary')); const t = useLoad(() => get('/api/dashboard/trends'))
  const v = useLoad(() => get('/api/dashboard/vendor-stats'))
  if (s.loading && !s.data) return <Spinner />
  const d = s.data
  return (<>
    <PageHeader title="Dashboard" sub="Live view of AP processing from the SQL database">
      <Link to="/review"><Btn variant="ghost"><ClipboardCheck className="h-4 w-4" />Review Queue{d?.pending_reviews ? ` (${d.pending_reviews})` : ''}</Btn></Link>
      <Link to="/add"><Btn><Plus className="h-4 w-4" />Add Invoice</Btn></Link>
    </PageHeader>
    <ErrorBox msg={s.err} />
    {d && <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
      <Stat label="Total invoices" value={d.total_invoices} icon={FileText} />
      <Stat label="Processed" value={d.processed} icon={CheckCircle2} tone="green" />
      <Stat label="Auto-approved for AP" value={d.auto_approved} icon={CheckCircle2} tone="green" />
      <Stat label="Needs review" value={d.needs_review} icon={ClipboardCheck} tone="amber" />
      <Stat label="Rejected / blocked" value={d.rejected_blocked} icon={ShieldAlert} tone="red" />
      <Stat label="Duplicates detected" value={d.duplicates_detected} icon={Copy} tone="amber" />
      <Stat label="Total invoice value" value={money(d.total_value)} icon={IndianRupee} />
      <Stat label="Outstanding" value={money(d.total_outstanding)} icon={Wallet} />
      <Stat label="Avg processing time" value={d.avg_processing_seconds != null ? `${d.avg_processing_seconds.toFixed(2)}s` : '—'} icon={Timer} />
      <Stat label="PO match rate" value={d.po_match_rate != null ? `${d.po_match_rate.toFixed(0)}%` : '—'} icon={Target} />
    </div>}
    <div className="mb-6 grid gap-4 lg:grid-cols-3">
      <Card title="Processing volume (30 days)" className="lg:col-span-2">
        <div className="h-64"><ResponsiveContainer><BarChart data={t.data?.volume || []}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} /><Tooltip /><Legend />
          {Object.keys(C).map(k => <Bar key={k} dataKey={k} stackId="a" fill={C[k]} />)}</BarChart></ResponsiveContainer></div></Card>
      <Card title="Decision distribution"><div className="h-64"><ResponsiveContainer><PieChart><Pie data={t.data?.distribution || []} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85}>
        {(t.data?.distribution || []).map((e: any) => <Cell key={e.name} fill={C[e.name] || '#94a3b8'} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer></div></Card>
      <Card title="Invoice value by vendor" className="lg:col-span-2"><div className="h-64"><ResponsiveContainer><BarChart data={v.data || []} layout="vertical" margin={{ left: 90 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" fontSize={11} /><YAxis type="category" dataKey="vendor" fontSize={11} width={150} /><Tooltip formatter={(x: any) => money(x)} /><Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer></div></Card>
      <Card title="Monthly outstanding"><div className="h-64"><ResponsiveContainer><BarChart data={(t.data?.monthly_outstanding || []).map((m: any) => ({ ...m, outstanding: Number(m.outstanding) }))}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} /><Tooltip formatter={(x: any) => money(x)} /><Bar dataKey="outstanding" fill="#f59e0b" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
    </div>
    <Card title="Recent activity" right={<Link to="/history" className="text-xs text-brand-600">View all</Link>}>
      <Table head={['Run', 'Invoice', 'Vendor', 'Source', 'Started', 'Decision']} empty={d?.recent?.length ? '' : 'No processing runs yet. Add an invoice to get started.'}>
        {(d?.recent || []).map((r: any) => <tr key={r.Run_ID} className="hover:bg-slate-50"><td className="px-3 py-2"><Link className="text-brand-600" to={`/runs/${r.Run_ID}`}>#{r.Run_ID}</Link></td>
          <td className="px-3 py-2">{r.Invoice_Number || '—'}</td><td className="px-3 py-2">{r.Vendor_Name || '—'}</td><td className="px-3 py-2">{r.Source_Type}</td>
          <td className="px-3 py-2">{dt(r.Started_At)}</td><td className="px-3 py-2"><Badge v={r.Final_Decision || r.Processing_Status} /></td></tr>)}
      </Table></Card>
  </>)
}
